"""
Email Template & Live Preview View for Marketing Mailer Desktop App.
Allows office staff to inspect, customize, and live-preview reminder emails.
"""

from pathlib import Path
from tkinter import messagebox
import customtkinter as ctk

from gui.theme import FONTS
from mailer.config import Config
from mailer.database import get_active_clients
from mailer.templates import create_reminder_message, render_string


class TemplateView(ctk.CTkFrame):
    """Template manager with live email preview and client interpolation."""

    def __init__(self, master, app_controller, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app_controller
        self.clients = []
        self._build_ui()
        self.load_clients_list()
        self.refresh_preview()

    def _build_ui(self):
        # Top Controls Card
        ctrl_card = ctk.CTkFrame(self, corner_radius=12, border_width=1, border_color=("gray80", "#334155"))
        ctrl_card.pack(fill="x", padx=15, pady=(15, 10))

        ctrl_inner = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        ctrl_inner.pack(fill="x", padx=16, pady=12)

        # Left: Client Selector for Preview
        lbl_preview_client = ctk.CTkLabel(ctrl_inner, text="Preview with Client:", font=FONTS["body_bold"])
        lbl_preview_client.pack(side="left", padx=(0, 8))

        self.client_combobox = ctk.CTkComboBox(
            ctrl_inner,
            values=["Sample Client"],
            font=FONTS["body"],
            width=240,
            command=lambda v: self.refresh_preview(),
        )
        self.client_combobox.pack(side="left", padx=(0, 16))

        # Subject Line Field
        lbl_subj = ctk.CTkLabel(ctrl_inner, text="Email Subject:", font=FONTS["body_bold"])
        lbl_subj.pack(side="left", padx=(0, 8))

        self.entry_subject = ctk.CTkEntry(
            ctrl_inner,
            font=FONTS["body"],
            width=260,
        )
        self.entry_subject.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.entry_subject.insert(0, Config.EMAIL_SUBJECT)

        # Send Preview Button
        btn_send_preview = ctk.CTkButton(
            ctrl_inner,
            text="✉ Send Test to Myself",
            font=("Segoe UI", 12, "bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            height=36,
            command=self._on_send_test,
        )
        btn_send_preview.pack(side="right")

        # Preview Container Card
        preview_card = ctk.CTkFrame(self, corner_radius=12, border_width=1, border_color=("gray80", "#334155"))
        preview_card.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        preview_header = ctk.CTkFrame(preview_card, fg_color="transparent")
        preview_header.pack(fill="x", padx=16, pady=(12, 6))

        lbl_title = ctk.CTkLabel(preview_header, text="Live Rendered Email Preview", font=FONTS["section_title"])
        lbl_title.pack(side="left")

        # Segmented button to switch between Formatted Plain Text & Raw HTML
        self.seg_view = ctk.CTkSegmentedButton(
            preview_header,
            values=["Readable Format", "HTML Source"],
            font=FONTS["caption"],
            command=lambda v: self.refresh_preview(),
        )
        self.seg_view.pack(side="right")
        self.seg_view.set("Readable Format")

        # Text Box Preview
        self.txt_preview = ctk.CTkTextbox(
            preview_card,
            font=("Segoe UI", 11),
            corner_radius=8,
            fg_color=("#f8fafc", "#0f172a"),
            text_color=("#1e293b", "#e2e8f0"),
        )
        self.txt_preview.pack(fill="both", expand=True, padx=16, pady=(0, 14))

    def load_clients_list(self):
        """Fetch active clients to populate selector dropdown."""
        self.clients = get_active_clients(Config.DATABASE_PATH)
        if self.clients:
            names = [f"{c['name']} ({c['company'] or c['email']})" for c in self.clients]
            self.client_combobox.configure(values=names)
            self.client_combobox.set(names[0])
        else:
            self.client_combobox.configure(values=["No Clients Added"])
            self.client_combobox.set("No Clients Added")

    def _get_selected_client_dict(self):
        val = self.client_combobox.get()
        for c in self.clients:
            tag = f"{c['name']} ({c['company'] or c['email']})"
            if tag == val:
                return c
        return {
            "name": "Valued Client",
            "email": "client@example.com",
            "company": "Apex Partner",
            "project_name": "Digital Marketing Strategy",
            "reminder_note": "Deliverables review and Q3 campaign milestone update.",
            "daily_limit": 100,
        }

    def refresh_preview(self):
        """Render template with selected client and display in preview area."""
        client = self._get_selected_client_dict()
        subject_prefix = self.entry_subject.get().strip() or Config.EMAIL_SUBJECT

        msg = create_reminder_message(
            client=client,
            sequence_num=1,
            sender_name=Config.SENDER_NAME,
            sender_email=Config.SENDER_EMAIL,
            subject_prefix=subject_prefix,
            html_template_path=Config.HTML_TEMPLATE_PATH,
            text_template_path=Config.TEXT_TEMPLATE_PATH,
        )

        mode = self.seg_view.get()
        content = ""

        # Extract parts
        for part in msg.walk():
            ct = part.get_content_type()
            if mode == "Readable Format" and ct == "text/plain":
                content = f"SUBJECT: {msg['Subject']}\n"
                content += f"FROM:    {msg['From']}\n"
                content += f"TO:      {msg['To']}\n"
                content += f"DATE:    {msg['Date']}\n"
                content += "=" * 60 + "\n\n"
                content += part.get_payload(decode=True).decode("utf-8", errors="ignore")
                break
            elif mode == "HTML Source" and ct == "text/html":
                content = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                break

        self.txt_preview.delete("1.0", "end")
        self.txt_preview.insert("1.0", content)

    def _on_send_test(self):
        """Send a test preview to staff's personal email."""
        dialog = ctk.CTkInputDialog(
            text="Enter your email to receive this exact preview:",
            title="Send Test Email Preview",
        )
        dest = dialog.get_input()
        if not dest or "@" not in dest:
            return

        client = self._get_selected_client_dict().copy()
        client["email"] = dest.strip()
        subject_prefix = self.entry_subject.get().strip() or Config.EMAIL_SUBJECT

        msg = create_reminder_message(
            client=client,
            sequence_num=1,
            sender_name=Config.SENDER_NAME,
            sender_email=Config.SENDER_EMAIL,
            subject_prefix=subject_prefix,
            html_template_path=Config.HTML_TEMPLATE_PATH,
            text_template_path=Config.TEXT_TEMPLATE_PATH,
        )

        ok, err = self.app.engine.smtp_client.send_email(Config.SENDER_EMAIL, dest.strip(), msg)
        if ok:
            messagebox.showinfo("Preview Delivered", f"Test reminder sent successfully to {dest}!", parent=self)
        else:
            messagebox.showerror("Send Failed", f"Could not send email: {err}", parent=self)

