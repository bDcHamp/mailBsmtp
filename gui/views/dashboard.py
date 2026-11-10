"""
Dashboard View for Marketing Mailer Desktop App.
Displays system state, metric cards, start/pause controls, and live activity stream.
"""

from datetime import datetime
import tkinter as tk
import customtkinter as ctk

from gui.theme import FONTS
from mailer.config import Config
from mailer.database import get_client_summary_stats


class DashboardView(ctk.CTkFrame):
    """Main dashboard displaying 24/7 service controls, KPI cards, and live logs."""

    def __init__(self, master, app_controller, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app_controller
        self._build_ui()
        self.refresh_stats()

    def _build_ui(self):
        # Top Control & Status Banner Card
        self.banner_card = ctk.CTkFrame(self, corner_radius=12, border_width=1, border_color=("gray80", "#334155"))
        self.banner_card.pack(fill="x", padx=15, pady=(15, 10))

        # Inner banner layout
        banner_inner = ctk.CTkFrame(self.banner_card, fg_color="transparent")
        banner_inner.pack(fill="x", padx=20, pady=16)

        # Left status text
        status_box = ctk.CTkFrame(banner_inner, fg_color="transparent")
        status_box.pack(side="left", fill="y")

        self.status_pill = ctk.CTkLabel(
            status_box,
            text="● SERVICE PAUSED",
            font=("Segoe UI", 12, "bold"),
            text_color="#ef4444",
            fg_color=("#fee2e2", "#450a0a"),
            corner_radius=8,
            padx=12,
            pady=4,
        )
        self.status_pill.pack(anchor="w", pady=(0, 4))

        self.status_desc = ctk.CTkLabel(
            status_box,
            text="The 24/7 engine is currently standing by. Click Start to resume work reminders.",
            font=FONTS["body"],
            text_color=("gray40", "#94a3b8"),
        )
        self.status_desc.pack(anchor="w")

        # Right control button
        self.btn_toggle_service = ctk.CTkButton(
            banner_inner,
            text="▶  Start 24/7 Reminders",
            font=("Segoe UI", 13, "bold"),
            fg_color="#10b981",
            hover_color="#059669",
            height=42,
            corner_radius=10,
            command=self._on_toggle_clicked,
        )
        self.btn_toggle_service.pack(side="right", padx=(20, 0))

        # 4 Metric Cards Grid
        metrics_grid = ctk.CTkFrame(self, fg_color="transparent")
        metrics_grid.pack(fill="x", padx=15, pady=5)
        metrics_grid.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="metric_cols")

        # 1. Active Clients Card
        self.card_clients, self.val_clients = self._create_metric_card(
            metrics_grid, col=0, title="ACTIVE CLIENTS", value="0", icon="👥", hint="Managed in roster"
        )
        # 2. Sent Today Card
        self.card_sent, self.val_sent = self._create_metric_card(
            metrics_grid, col=1, title="DELIVERED (24H)", value="0", icon="✉️", hint="Rolling 24h count"
        )
        # 3. Quota Remaining Card
        self.card_quota, self.val_quota = self._create_metric_card(
            metrics_grid, col=2, title="QUOTA REMAINING", value="0", icon="⏳", hint="Available today"
        )
        # 4. Webmail Relay Card
        self.card_relay, self.val_relay = self._create_metric_card(
            metrics_grid, col=3, title="WEBMAIL RELAY", value="Ready", icon="⚡", hint=Config.SMTP_HOST
        )

        # Live Activity Stream Card
        feed_card = ctk.CTkFrame(self, corner_radius=12, border_width=1, border_color=("gray80", "#334155"))
        feed_card.pack(fill="both", expand=True, padx=15, pady=(10, 15))

        feed_header = ctk.CTkFrame(feed_card, fg_color="transparent")
        feed_header.pack(fill="x", padx=16, pady=(12, 6))

        feed_title = ctk.CTkLabel(feed_header, text="Live Transmission Feed", font=FONTS["section_title"])
        feed_title.pack(side="left")

        btn_clear_log = ctk.CTkButton(
            feed_header,
            text="Clear Feed",
            font=FONTS["caption"],
            width=75,
            height=26,
            fg_color=("gray85", "#334155"),
            hover_color=("gray75", "#475569"),
            text_color=("gray20", "#f8fafc"),
            command=self.clear_logs,
        )
        btn_clear_log.pack(side="right")

        # Scrollable Text Console for logs
        self.log_textbox = ctk.CTkTextbox(
            feed_card,
            font=("Consolas", 11),
            corner_radius=8,
            border_width=0,
            fg_color=("#f8fafc", "#0f172a"),
            text_color=("#1e293b", "#e2e8f0"),
        )
        self.log_textbox.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        self.log_textbox.configure(state="disabled")

        self.log("System initialized. Ready to begin 24/7 marketing work reminders.")

    def _create_metric_card(self, parent, col, title, value, icon, hint):
        card = ctk.CTkFrame(parent, corner_radius=12, border_width=1, border_color=("gray80", "#334155"))
        card.grid(row=0, column=col, padx=5, pady=5, sticky="nsew")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=12)

        top_row = ctk.CTkFrame(inner, fg_color="transparent")
        top_row.pack(fill="x")

        lbl_title = ctk.CTkLabel(
            top_row,
            text=title,
            font=FONTS["card_title"],
            text_color=("gray40", "#94a3b8")
        )
        lbl_title.pack(side="left")

        lbl_icon = ctk.CTkLabel(top_row, text=icon, font=("Segoe UI Emoji", 14))
        lbl_icon.pack(side="right")

        lbl_val = ctk.CTkLabel(inner, text=value, font=FONTS["metric_value"], anchor="w")
        lbl_val.pack(fill="x", pady=(4, 2))

        lbl_hint = ctk.CTkLabel(inner, text=hint, font=FONTS["caption"], text_color=("gray50", "#64748b"), anchor="w")
        lbl_hint.pack(fill="x")

        return card, lbl_val

    def _on_toggle_clicked(self):
        if self.app.is_engine_running:
            self.app.stop_engine()
        else:
            self.app.start_engine()

    def update_engine_status(self, is_running: bool):
        if is_running:
            self.status_pill.configure(
                text="● 24/7 SERVICE ACTIVE",
                text_color="#10b981",
                fg_color=("#d1fae5", "#064e3b"),
            )
            self.status_desc.configure(
                text="The 24/7 dispatcher is actively pacing and sending work reminders to clients."
            )
            self.btn_toggle_service.configure(
                text="⏸  Pause Service",
                fg_color="#ef4444",
                hover_color="#dc2626",
            )
        else:
            self.status_pill.configure(
                text="● SERVICE PAUSED",
                text_color="#ef4444",
                fg_color=("#fee2e2", "#450a0a"),
            )
            self.status_desc.configure(
                text="The 24/7 engine is currently standing by. Click Start to resume work reminders."
            )
            self.btn_toggle_service.configure(
                text="▶  Start 24/7 Reminders",
                fg_color="#10b981",
                hover_color="#059669",
            )

    def refresh_stats(self):
        """Query database and update metric cards."""
        try:
            stats = get_client_summary_stats(Config.DATABASE_PATH, Config.WINDOW_HOURS)
            total_clients = len(stats)
            active_clients = sum(1 for s in stats if s["is_active"])
            total_sent = sum(s["sent_24h"] for s in stats)
            total_remaining = sum(s["remaining_quota"] for s in stats if s["is_active"])

            self.val_clients.configure(text=str(active_clients))
            self.val_sent.configure(text=f"{total_sent:,}")
            self.val_quota.configure(text=f"{total_remaining:,}")
        except Exception:
            pass

    def log(self, message: str, level: str = "INFO"):
        """Append a message to the live activity stream."""
        now = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{now}]"
        line = f"{prefix} {message}\n"

        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", line)
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def clear_logs(self):
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")

