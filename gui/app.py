"""
Main Desktop Application Window.
Coordinates background dispatch thread, tab navigation, and system tray lifecycle.
"""

from datetime import datetime
from pathlib import Path
import queue
import sys
import threading
import time
from tkinter import messagebox
import customtkinter as ctk

from gui.theme import FONTS, apply_theme
from gui.tray import SystemTrayManager
from gui.views import ClientsView, DashboardView, SettingsView, TemplateView
from mailer.config import Config
from mailer.database import (
    get_active_clients,
    get_client_sends_in_window,
    init_db,
    record_delivery,
)
from mailer.engine import DispatchEngine
from mailer.templates import create_reminder_message


class MarketingMailerApp(ctk.CTk):
    """Primary desktop application controller."""

    def __init__(self):
        super().__init__()
        apply_theme("Dark")

        self.title("Marketing SMTP Work Reminder System")
        self.geometry("1100x720")
        self.minsize(980, 620)

        # Set window icon
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "app_icon.ico"
        if icon_path.is_file():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

        # Initialize local database
        init_db(Config.DATABASE_PATH)

        # Engine & Threading
        self.engine = DispatchEngine(Config)
        self.is_engine_running = False
        self._engine_thread = None
        self.log_queue = queue.Queue()

        # System Tray Manager
        self.tray_manager = SystemTrayManager(self)

        self._build_shell()
        self._schedule_periodic_updates()

        # Intercept window close
        self.protocol("WM_DELETE_WINDOW", self.on_close_requested)

    def _build_shell(self):
        # Top Header Bar
        self.header_bar = ctk.CTkFrame(self, height=56, corner_radius=0, fg_color=("#e2e8f0", "#1e293b"))
        self.header_bar.pack(fill="x", side="top")

        # Title & Branding
        brand_box = ctk.CTkFrame(self.header_bar, fg_color="transparent")
        brand_box.pack(side="left", padx=16, pady=10)

        lbl_logo = ctk.CTkLabel(brand_box, text="⚡", font=("Segoe UI Emoji", 18))
        lbl_logo.pack(side="left", padx=(0, 6))

        lbl_app_name = ctk.CTkLabel(brand_box, text="Marketing Mailer", font=FONTS["app_title"])
        lbl_app_name.pack(side="left")

        lbl_badge = ctk.CTkLabel(
            brand_box,
            text="v2.0",
            font=FONTS["caption"],
            text_color=("gray40", "#94a3b8"),
            fg_color=("gray80", "#334155"),
            corner_radius=6,
            padx=6,
            pady=2,
        )
        lbl_badge.pack(side="left", padx=(8, 0))

        # Top Navigation Segmented Button
        nav_box = ctk.CTkFrame(self.header_bar, fg_color="transparent")
        nav_box.pack(side="right", padx=16, pady=10)

        self.nav_tabs = ctk.CTkSegmentedButton(
            nav_box,
            values=["📊  Dashboard", "👥  Clients (30)", "✉️  Email Template", "⚙️  Settings"],
            font=("Segoe UI", 12, "bold"),
            height=34,
            command=self._on_tab_changed,
        )
        self.nav_tabs.pack(side="right")
        self.nav_tabs.set("📊  Dashboard")

        # Main Content Container
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.pack(fill="both", expand=True)

        # Instantiate View Frames
        self.dashboard_view = DashboardView(self.content_container, app_controller=self)
        self.clients_view = ClientsView(self.content_container, app_controller=self)
        self.template_view = TemplateView(self.content_container, app_controller=self)
        self.settings_view = SettingsView(self.content_container, app_controller=self)

        self.views = {
            "📊  Dashboard": self.dashboard_view,
            "👥  Clients (30)": self.clients_view,
            "✉️  Email Template": self.template_view,
            "⚙️  Settings": self.settings_view,
        }

        # Show initial view
        self.dashboard_view.pack(fill="both", expand=True)

    def _on_tab_changed(self, tab_name):
        for view in self.views.values():
            view.pack_forget()

        active_view = self.views.get(tab_name)
        if active_view:
            active_view.pack(fill="both", expand=True)

            if tab_name == "👥  Clients (30)":
                self.clients_view.reload_clients()
            elif tab_name == "✉️  Email Template":
                self.template_view.load_clients_list()
                self.template_view.refresh_preview()
            elif tab_name == "📊  Dashboard":
                self.dashboard_view.refresh_stats()

    def start_engine(self):
        """Start the 24/7 background dispatch loop in a background thread."""
        if self.is_engine_running:
            return

        self.is_engine_running = True
        self.engine.stop_event.clear()
        self.dashboard_view.update_engine_status(True)
        self.dashboard_view.log("Starting 24/7 continuous work reminder engine...")

        def _worker_loop():
            # Initial connection check
            ok, msg = self.engine.smtp_client.test_connection()
            if ok:
                self.log_queue.put(("SUCCESS", f"Connected to Webmail SMTP: {Config.SMTP_HOST}:{Config.SMTP_PORT}"))
            else:
                self.log_queue.put(("WARN", f"Webmail connection warning: {msg}"))

            while not self.engine.stop_event.is_set():
                try:
                    clients = get_active_clients(Config.DATABASE_PATH)
                    if not clients:
                        self.log_queue.put(("INFO", "No active clients in roster. Sleeping 15s..."))
                        self.engine.stop_event.wait(15.0)
                        continue

                    dispatched_count = 0
                    now = time.time()

                    for client in clients:
                        if self.engine.stop_event.is_set():
                            break

                        if self.engine.is_client_due(client, now):
                            cid = client["client_id"]
                            recipient = client["email"]
                            name = client.get("name", recipient)
                            limit = client.get("daily_limit", Config.DAILY_CAP_PER_CLIENT)

                            sent_in_window = get_client_sends_in_window(cid, Config.WINDOW_HOURS, Config.DATABASE_PATH)
                            seq = sent_in_window + 1

                            self.log_queue.put(("INFO", f"Sending reminder #{seq}/{limit} to {name} ({recipient})..."))

                            msg = create_reminder_message(
                                client=client,
                                sequence_num=seq,
                                sender_name=Config.SENDER_NAME,
                                sender_email=Config.SENDER_EMAIL,
                                subject_prefix=Config.EMAIL_SUBJECT,
                                html_template_path=Config.HTML_TEMPLATE_PATH,
                                text_template_path=Config.TEXT_TEMPLATE_PATH,
                            )

                            success, err = self.engine.smtp_client.send_email(
                                sender=Config.SENDER_EMAIL,
                                recipient=recipient,
                                message=msg,
                            )

                            if success:
                                record_delivery(
                                    client_id=cid,
                                    recipient_email=recipient,
                                    subject=msg["Subject"],
                                    sequence_num=seq,
                                    status="SUCCESS",
                                    error_message=None,
                                    db_path=Config.DATABASE_PATH,
                                )
                                rem = max(0, limit - seq)
                                self.log_queue.put(("SUCCESS", f"Delivered to {name}! (Remaining 24h Quota: {rem})"))
                            else:
                                record_delivery(
                                    client_id=cid,
                                    recipient_email=recipient,
                                    subject=msg["Subject"],
                                    sequence_num=seq,
                                    status="FAILED",
                                    error_message=err,
                                    db_path=Config.DATABASE_PATH,
                                )
                                self.log_queue.put(("ERROR", f"Delivery failed for {name}: {err}"))

                            dispatched_count += 1
                            if Config.GLOBAL_DISPATCH_DELAY > 0:
                                self.engine.stop_event.wait(Config.GLOBAL_DISPATCH_DELAY)

                    if dispatched_count == 0:
                        self.engine.stop_event.wait(5.0)

                except Exception as e:
                    self.log_queue.put(("ERROR", f"Engine error: {e}"))
                    self.engine.stop_event.wait(10.0)

            self.log_queue.put(("INFO", "24/7 Dispatcher thread stopped."))

        self._engine_thread = threading.Thread(target=_worker_loop, daemon=True)
        self._engine_thread.start()

    def stop_engine(self):
        """Halt the 24/7 background dispatch loop."""
        if not self.is_engine_running:
            return

        self.engine.stop_event.set()
        self.is_engine_running = False
        self.dashboard_view.update_engine_status(False)
        self.dashboard_view.log("24/7 Service paused by user.")

    def _schedule_periodic_updates(self):
        """Process log messages and refresh metric cards every 500ms."""
        while not self.log_queue.empty():
            try:
                level, msg = self.log_queue.get_nowait()
                self.dashboard_view.log(msg, level)
                self.dashboard_view.refresh_stats()
            except queue.Empty:
                break

        # Check again in 500ms
        self.after(500, self._schedule_periodic_updates)

    def on_close_requested(self):
        """
        Handle window close event:
        Presents a friendly choice to minimize to system tray (recommended for 24/7)
        or completely exit.
        """
        msg = (
            "The Marketing Mailer system is configured for 24/7 work reminders.\n\n"
            "• Minimize to Tray: Keeps the 24/7 reminder engine running in the background.\n"
            "• Exit Completely: Halts all scheduled reminders.\n\n"
            "Would you like to keep the 24/7 system running in the background?"
        )
        answer = messagebox.askyesnocancel("Exit or Run in Background", msg, parent=self)

        if answer is True:
            # Yes -> Minimize to tray
            self.minimize_to_tray()
        elif answer is False:
            # No -> Exit completely
            self.quit_app()
        # Cancel -> Do nothing, stay open

    def minimize_to_tray(self):
        """Hide main window and activate system tray icon."""
        self.withdraw()
        self.tray_manager.start()

    def restore_from_tray(self):
        """Restore main window from system tray."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def quit_app(self):
        """Cleanly terminate engine and close window."""
        self.stop_engine()
        self.tray_manager.stop()
        self.destroy()
        sys.exit(0)


def launch_gui():
    """Entry point to launch desktop application."""
    app = MarketingMailerApp()
    app.mainloop()


if __name__ == "__main__":
    launch_gui()
