"""
Settings View for Marketing Mailer Desktop App.
Allows staff to configure Webmail SMTP, sender profiles, rate limits, and theme appearance.
"""

import os
from pathlib import Path
from tkinter import messagebox
import customtkinter as ctk

from gui.theme import FONTS
from mailer.config import BASE_DIR, Config
from mailer.smtp_client import SMTPClient


class SettingsView(ctk.CTkScrollableFrame):
    """Configuration panel for Webmail SMTP, sender identity, and system rates."""

    def __init__(self, master, app_controller, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app_controller
        self._build_ui()
        self.load_settings()

    def _build_ui(self):
        # 1. Webmail SMTP Server Section Card
        smtp_card = ctk.CTkFrame(self, corner_radius=12, border_width=1, border_color=("gray80", "#334155"))
        smtp_card.pack(fill="x", padx=15, pady=(15, 10))

        smtp_inner = ctk.CTkFrame(smtp_card, fg_color="transparent")
        smtp_inner.pack(fill="x", padx=20, pady=16)

        lbl_smtp_title = ctk.CTkLabel(smtp_inner, text="Webmail SMTP Server Configuration", font=FONTS["section_title"])
        lbl_smtp_title.pack(anchor="w", pady=(0, 10))

        # Grid for Host & Port
        hp_grid = ctk.CTkFrame(smtp_inner, fg_color="transparent")
        hp_grid.pack(fill="x", pady=4)
        hp_grid.grid_columnconfigure(0, weight=3)
        hp_grid.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hp_grid, text="SMTP Host (e.g. mail.domain.com):", font=FONTS["body_bold"]).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hp_grid, text="Port (465 SSL or 587 TLS):", font=FONTS["body_bold"]).grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.entry_host = ctk.CTkEntry(hp_grid, font=FONTS["body"], height=34)
        self.entry_host.grid(row=1, column=0, sticky="ew", pady=(2, 8))

        self.entry_port = ctk.CTkEntry(hp_grid, font=FONTS["body"], height=34)
        self.entry_port.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(2, 8))

        # Username & Password
        ctk.CTkLabel(smtp_inner, text="Webmail Username / Email:", font=FONTS["body_bold"]).pack(anchor="w", pady=(4, 2))
        self.entry_user = ctk.CTkEntry(smtp_inner, font=FONTS["body"], height=34)
        self.entry_user.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(smtp_inner, text="Webmail Password:", font=FONTS["body_bold"]).pack(anchor="w", pady=(4, 2))
        
        pwd_box = ctk.CTkFrame(smtp_inner, fg_color="transparent")
        pwd_box.pack(fill="x", pady=(0, 8))
        self.entry_pass = ctk.CTkEntry(pwd_box, font=FONTS["body"], height=34, show="•")
        self.entry_pass.pack(side="left", fill="x", expand=True)

        self.var_show_pwd = ctk.BooleanVar(value=False)
        chk_show = ctk.CTkCheckBox(
            pwd_box,
            text="Show",
            variable=self.var_show_pwd,
            width=65,
            command=self._toggle_pwd_visibility,
        )
        chk_show.pack(side="right", padx=(10, 0))

        # SSL & TLS switches
        sec_box = ctk.CTkFrame(smtp_inner, fg_color="transparent")
        sec_box.pack(fill="x", pady=6)
        self.var_ssl = ctk.BooleanVar(value=True)
        self.var_tls = ctk.BooleanVar(value=False)

        chk_ssl = ctk.CTkSwitch(sec_box, text="Direct SSL Encryption (Port 465)", variable=self.var_ssl, font=FONTS["body"])
        chk_ssl.pack(side="left", padx=(0, 20))

        chk_tls = ctk.CTkSwitch(sec_box, text="STARTTLS Encryption (Port 587)", variable=self.var_tls, font=FONTS["body"])
        chk_tls.pack(side="left")

        # Test Connection Button & Status Badge
        test_box = ctk.CTkFrame(smtp_inner, fg_color="transparent")
        test_box.pack(fill="x", pady=(12, 0))

        self.btn_test = ctk.CTkButton(
            test_box,
            text="🔍  Test Webmail Connection",
            font=("Segoe UI", 12, "bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            height=36,
            command=self._test_connection,
        )
        self.btn_test.pack(side="left")

        self.lbl_test_result = ctk.CTkLabel(test_box, text="", font=FONTS["body"], anchor="w")
        self.lbl_test_result.pack(side="left", padx=(15, 0))

        # 2. Sender Profile Section Card
        sender_card = ctk.CTkFrame(self, corner_radius=12, border_width=1, border_color=("gray80", "#334155"))
        sender_card.pack(fill="x", padx=15, pady=10)

        sender_inner = ctk.CTkFrame(sender_card, fg_color="transparent")
        sender_inner.pack(fill="x", padx=20, pady=16)

        lbl_sender_title = ctk.CTkLabel(sender_inner, text="Agency Sender Identity", font=FONTS["section_title"])
        lbl_sender_title.pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(sender_inner, text="Sender Display Name (e.g. Marketing Operations):", font=FONTS["body_bold"]).pack(anchor="w", pady=(4, 2))
        self.entry_sender_name = ctk.CTkEntry(sender_inner, font=FONTS["body"], height=34)
        self.entry_sender_name.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(sender_inner, text="Sender Email Address (From):", font=FONTS["body_bold"]).pack(anchor="w", pady=(4, 2))
        self.entry_sender_email = ctk.CTkEntry(sender_inner, font=FONTS["body"], height=34)
        self.entry_sender_email.pack(fill="x", pady=(0, 8))

        # 3. Quota & Timing Rules Card
        rules_card = ctk.CTkFrame(self, corner_radius=12, border_width=1, border_color=("gray80", "#334155"))
        rules_card.pack(fill="x", padx=15, pady=10)

        rules_inner = ctk.CTkFrame(rules_card, fg_color="transparent")
        rules_inner.pack(fill="x", padx=20, pady=16)

        lbl_rules_title = ctk.CTkLabel(rules_inner, text="Delivery Rules & 24h Limits", font=FONTS["section_title"])
        lbl_rules_title.pack(anchor="w", pady=(0, 10))

        r_grid = ctk.CTkFrame(rules_inner, fg_color="transparent")
        r_grid.pack(fill="x")
        r_grid.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(r_grid, text="Daily Limit per Client (Max Emails/24h):", font=FONTS["body_bold"]).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(r_grid, text="Inter-Dispatch Delay (seconds):", font=FONTS["body_bold"]).grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.entry_daily_cap = ctk.CTkEntry(r_grid, font=FONTS["body"], height=34)
        self.entry_daily_cap.grid(row=1, column=0, sticky="ew", pady=(2, 8))

        self.entry_delay = ctk.CTkEntry(r_grid, font=FONTS["body"], height=34)
        self.entry_delay.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(2, 8))

        # 4. Appearance & Theme Card
        theme_card = ctk.CTkFrame(self, corner_radius=12, border_width=1, border_color=("gray80", "#334155"))
        theme_card.pack(fill="x", padx=15, pady=10)

        theme_inner = ctk.CTkFrame(theme_card, fg_color="transparent")
        theme_inner.pack(fill="x", padx=20, pady=16)

        lbl_theme_title = ctk.CTkLabel(theme_inner, text="Appearance & Office Display Theme", font=FONTS["section_title"])
        lbl_theme_title.pack(anchor="w", pady=(0, 10))

        theme_box = ctk.CTkFrame(theme_inner, fg_color="transparent")
        theme_box.pack(fill="x")

        ctk.CTkLabel(theme_box, text="Select Interface Theme:", font=FONTS["body_bold"]).pack(side="left", padx=(0, 15))

        self.seg_theme = ctk.CTkSegmentedButton(
            theme_box,
            values=["🌙 Dark Theme", "☀️ Light Theme", "💻 System"],
            font=FONTS["body"],
            command=self._on_theme_changed,
        )
        self.seg_theme.pack(side="left")
        self.seg_theme.set("🌙 Dark Theme")

        # Save Settings Bottom Bar
        save_card = ctk.CTkFrame(self, fg_color="transparent")
        save_card.pack(fill="x", padx=15, pady=(15, 25))

        btn_save = ctk.CTkButton(
            save_card,
            text="💾  Save Settings & Apply Immediately",
            font=("Segoe UI", 13, "bold"),
            fg_color="#10b981",
            hover_color="#059669",
            height=44,
            command=self.save_settings,
        )
        btn_save.pack(side="right")

    def _toggle_pwd_visibility(self):
        show_char = "" if self.var_show_pwd.get() else "•"
        self.entry_pass.configure(show=show_char)

    def load_settings(self):
        """Populate form fields with current Config settings."""
        self.entry_host.insert(0, Config.SMTP_HOST)
        self.entry_port.insert(0, str(Config.SMTP_PORT))
        self.entry_user.insert(0, Config.SMTP_USER)
        self.entry_pass.insert(0, Config.SMTP_PASSWORD)
        self.var_ssl.set(Config.SMTP_USE_SSL)
        self.var_tls.set(Config.SMTP_USE_TLS)

        self.entry_sender_name.insert(0, Config.SENDER_NAME)
        self.entry_sender_email.insert(0, Config.SENDER_EMAIL)

        self.entry_daily_cap.insert(0, str(Config.DAILY_CAP_PER_CLIENT))
        self.entry_delay.insert(0, str(Config.GLOBAL_DISPATCH_DELAY))

    def _on_theme_changed(self, mode_str):
        if "Dark" in mode_str:
            ctk.set_appearance_mode("Dark")
        elif "Light" in mode_str:
            ctk.set_appearance_mode("Light")
        else:
            ctk.set_appearance_mode("System")

    def _test_connection(self):
        host = self.entry_host.get().strip()
        try:
            port = int(self.entry_port.get().strip())
        except ValueError:
            port = 465
        user = self.entry_user.get().strip()
        pwd = self.entry_pass.get().strip()
        use_ssl = self.var_ssl.get()
        use_tls = self.var_tls.get()

        self.lbl_test_result.configure(text="Connecting to Webmail...", text_color="#3b82f6")
        self.update_idletasks()

        client = SMTPClient(
            host=host,
            port=port,
            username=user,
            password=pwd,
            use_ssl=use_ssl,
            use_tls=use_tls,
            timeout=15,
        )
        ok, msg = client.test_connection()

        if ok:
            self.lbl_test_result.configure(
                text="✔ Connection & Login Successful!",
                text_color="#10b981",
            )
        else:
            clean_err = msg.split("\n")[0][:70]
            self.lbl_test_result.configure(
                text=f"✖ {clean_err}",
                text_color="#ef4444",
            )

    def save_settings(self):
        """Write configuration to .env file and update running Config."""
        host = self.entry_host.get().strip()
        port = self.entry_port.get().strip() or "465"
        user = self.entry_user.get().strip()
        pwd = self.entry_pass.get().strip()
        use_ssl = "true" if self.var_ssl.get() else "false"
        use_tls = "true" if self.var_tls.get() else "false"

        s_name = self.entry_sender_name.get().strip() or "Marketing Operations Team"
        s_email = self.entry_sender_email.get().strip() or user

        daily_cap = self.entry_daily_cap.get().strip() or "100"
        delay = self.entry_delay.get().strip() or "2.0"

        # Update running Config
        Config.SMTP_HOST = host
        Config.SMTP_PORT = int(port)
        Config.SMTP_USER = user
        Config.SMTP_PASSWORD = pwd
        Config.SMTP_USE_SSL = self.var_ssl.get()
        Config.SMTP_USE_TLS = self.var_tls.get()
        Config.SENDER_NAME = s_name
        Config.SENDER_EMAIL = s_email
        Config.DAILY_CAP_PER_CLIENT = int(daily_cap)
        Config.GLOBAL_DISPATCH_DELAY = float(delay)

        # Update engine's SMTP client
        self.app.engine.smtp_client = SMTPClient(
            host=Config.SMTP_HOST,
            port=Config.SMTP_PORT,
            username=Config.SMTP_USER,
            password=Config.SMTP_PASSWORD,
            use_ssl=Config.SMTP_USE_SSL,
            use_tls=Config.SMTP_USE_TLS,
        )

        # Persist to .env
        env_content = f"""# Marketing Mailer Webmail Settings
SMTP_HOST={host}
SMTP_PORT={port}
SMTP_USER={user}
SMTP_PASSWORD={pwd}
SMTP_USE_SSL={use_ssl}
SMTP_USE_TLS={use_tls}

SENDER_NAME={s_name}
SENDER_EMAIL={s_email}

DAILY_CAP_PER_CLIENT={daily_cap}
WINDOW_HOURS=24.0
GLOBAL_DISPATCH_DELAY={delay}
"""
        env_path = BASE_DIR / ".env"
        try:
            env_path.write_text(env_content, encoding="utf-8")
            messagebox.showinfo("Settings Saved", "Settings successfully saved and applied to the 24/7 service!", parent=self)
            self.app.dashboard_view.val_relay.configure(hint=host)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not write .env: {e}", parent=self)

