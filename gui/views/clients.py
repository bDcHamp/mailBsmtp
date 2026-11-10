"""
Client Roster View for Marketing Mailer Desktop App.
Allows office staff to view, search, add, edit, and import/export clients.
"""

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
import customtkinter as ctk

from gui.theme import FONTS
from mailer.clients import sync_clients
from mailer.config import Config
from mailer.database import get_all_clients, get_client_summary_stats, upsert_client


class ClientEditDialog(ctk.CTkToplevel):
    """Modal dialog to add or edit client details."""

    def __init__(self, master, client_data=None, on_save_callback=None):
        super().__init__(master)
        self.client_data = client_data or {}
        self.on_save = on_save_callback

        is_edit = bool(client_data and client_data.get("email"))
        self.title("Edit Client" if is_edit else "Add New Client")
        self.geometry("520x560")
        self.resizable(False, False)
        self.grab_set()

        self._build_form(is_edit)

    def _build_form(self, is_edit):
        pad_x = 24
        header = ctk.CTkLabel(
            self,
            text="Client Details & Work Notes" if is_edit else "Add New Client to Roster",
            font=FONTS["section_title"],
            anchor="w",
        )
        header.pack(fill="x", padx=pad_x, pady=(20, 15))

        form_frame = ctk.CTkFrame(self, fg_color="transparent")
        form_frame.pack(fill="both", expand=True, padx=pad_x)

        # Name
        self.entry_name = self._add_field(form_frame, "Client Contact Name:", self.client_data.get("name", ""))

        # Email
        self.entry_email = self._add_field(form_frame, "Client Email Address:", self.client_data.get("email", ""))
        if is_edit:
            self.entry_email.configure(state="disabled")

        # Company
        self.entry_company = self._add_field(form_frame, "Company / Brand Name:", self.client_data.get("company", ""))

        # Project Name
        self.entry_project = self._add_field(form_frame, "Project / Campaign Scope:", self.client_data.get("project_name", "Marketing Campaign"))

        # Daily Limit
        self.entry_limit = self._add_field(form_frame, "Daily Limit (Emails in 24h):", str(self.client_data.get("daily_limit", 100)))

        # Work Reminder Note
        lbl_note = ctk.CTkLabel(form_frame, text="Current Work Item / Milestone Note:", font=FONTS["body_bold"], anchor="w")
        lbl_note.pack(fill="x", pady=(8, 2))
        self.txt_note = ctk.CTkTextbox(form_frame, height=75, font=FONTS["body"])
        self.txt_note.pack(fill="x", pady=(0, 10))
        self.txt_note.insert("1.0", self.client_data.get("reminder_note", "Regular work progress and campaign monitoring."))

        # Active Toggle
        self.var_active = ctk.BooleanVar(value=bool(self.client_data.get("is_active", 1)))
        self.chk_active = ctk.CTkCheckBox(form_frame, text="Active (Send scheduled reminders)", variable=self.var_active, font=FONTS["body"])
        self.chk_active.pack(anchor="w", pady=(2, 15))

        # Bottom Buttons
        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(fill="x", padx=pad_x, pady=(0, 20))

        btn_cancel = ctk.CTkButton(
            btn_box,
            text="Cancel",
            fg_color=("gray80", "#334155"),
            text_color=("gray20", "#f8fafc"),
            hover_color=("gray70", "#475569"),
            width=100,
            command=self.destroy,
        )
        btn_cancel.pack(side="left")

        btn_save = ctk.CTkButton(
            btn_box,
            text="Save Client",
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            width=120,
            command=self._save,
        )
        btn_save.pack(side="right")

    def _add_field(self, parent, label_text, default_val):
        lbl = ctk.CTkLabel(parent, text=label_text, font=FONTS["body_bold"], anchor="w")
        lbl.pack(fill="x", pady=(4, 2))
        entry = ctk.CTkEntry(parent, font=FONTS["body"], height=34)
        entry.pack(fill="x", pady=(0, 4))
        entry.insert(0, str(default_val))
        return entry

    def _save(self):
        email = self.entry_email.get().strip()
        name = self.entry_name.get().strip()
        company = self.entry_company.get().strip()
        project = self.entry_project.get().strip()
        note = self.txt_note.get("1.0", "end").strip()

        if not email or "@" not in email:
            messagebox.showerror("Invalid Input", "Please provide a valid email address.", parent=self)
            return

        try:
            limit = int(self.entry_limit.get().strip() or "100")
        except ValueError:
            limit = 100

        client_dict = {
            "client_id": email.lower(),
            "name": name or email.split("@")[0].title(),
            "email": email,
            "company": company,
            "project_name": project,
            "reminder_note": note,
            "daily_limit": limit,
            "is_active": 1 if self.var_active.get() else 0,
        }

        upsert_client(client_dict, Config.DATABASE_PATH)
        if self.on_save:
            self.on_save()
        self.destroy()


class ClientsView(ctk.CTkFrame):
    """Client roster management view."""

    def __init__(self, master, app_controller, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app_controller
        self.all_stats = []
        self._build_ui()
        self.reload_clients()

    def _build_ui(self):
        # Action Bar Card
        bar_card = ctk.CTkFrame(self, corner_radius=12, border_width=1, border_color=("gray80", "#334155"))
        bar_card.pack(fill="x", padx=15, pady=(15, 10))

        bar_inner = ctk.CTkFrame(bar_card, fg_color="transparent")
        bar_inner.pack(fill="x", padx=16, pady=12)

        # Search Bar
        self.search_entry = ctk.CTkEntry(
            bar_inner,
            placeholder_text="🔍 Search clients by name, company, or email...",
            font=FONTS["body"],
            width=320,
            height=36,
        )
        self.search_entry.pack(side="left")
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_table())

        # Buttons on Right
        btn_add = ctk.CTkButton(
            bar_inner,
            text="+ Add Client",
            font=("Segoe UI", 12, "bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            height=36,
            command=self._on_add_client,
        )
        btn_add.pack(side="right", padx=(8, 0))

        btn_edit = ctk.CTkButton(
            bar_inner,
            text="✏ Edit",
            font=FONTS["body"],
            fg_color=("gray80", "#334155"),
            text_color=("gray20", "#f8fafc"),
            hover_color=("gray70", "#475569"),
            height=36,
            width=75,
            command=self._on_edit_selected,
        )
        btn_edit.pack(side="right", padx=(8, 0))

        btn_toggle = ctk.CTkButton(
            bar_inner,
            text="Active/Pause",
            font=FONTS["body"],
            fg_color=("gray80", "#334155"),
            text_color=("gray20", "#f8fafc"),
            hover_color=("gray70", "#475569"),
            height=36,
            width=100,
            command=self._on_toggle_active,
        )
        btn_toggle.pack(side="right", padx=(8, 0))

        btn_sync = ctk.CTkButton(
            bar_inner,
            text="🔄 Sync CSV",
            font=FONTS["body"],
            fg_color=("gray80", "#334155"),
            text_color=("gray20", "#f8fafc"),
            hover_color=("gray70", "#475569"),
            height=36,
            width=90,
            command=self._on_sync_csv,
        )
        btn_sync.pack(side="right", padx=(8, 0))

        # Table Container Card
        table_card = ctk.CTkFrame(self, corner_radius=12, border_width=1, border_color=("gray80", "#334155"))
        table_card.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # ttk.Treeview setup for table
        columns = ("status", "name", "email", "company", "project", "note", "quota")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("status", text="Status")
        self.tree.heading("name", text="Client Name")
        self.tree.heading("email", text="Email")
        self.tree.heading("company", text="Company")
        self.tree.heading("project", text="Project Scope")
        self.tree.heading("note", text="Work Milestone Note")
        self.tree.heading("quota", text="24h Quota (Sent/Max)")

        self.tree.column("status", width=70, anchor="center")
        self.tree.column("name", width=140)
        self.tree.column("email", width=170)
        self.tree.column("company", width=130)
        self.tree.column("project", width=140)
        self.tree.column("note", width=220)
        self.tree.column("quota", width=120, anchor="center")

        # Scrollbar
        scrollbar = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=12)
        scrollbar.pack(side="right", fill="y", padx=(0, 12), pady=12)

        self.tree.bind("<Double-1>", lambda e: self._on_edit_selected())

    def reload_clients(self):
        """Fetch all clients from database and populate treeview."""
        self.all_stats = get_client_summary_stats(Config.DATABASE_PATH, Config.WINDOW_HOURS)
        self._filter_table()

    def _filter_table(self):
        query = self.search_entry.get().strip().lower()
        for item in self.tree.get_children():
            self.tree.delete(item)

        for s in self.all_stats:
            match = (
                not query
                or query in s["name"].lower()
                or query in s["email"].lower()
                or query in s["company"].lower()
                or query in s.get("project_name", "").lower()
            )
            if not match:
                continue

            status_str = "🟢 Active" if s["is_active"] else "⏸ Paused"
            quota_str = f"{s['sent_24h']} / {s['daily_limit']}"

            # Fetch extra fields like project_name and reminder_note
            # from clients list
            client_record = next((c for c in get_all_clients(Config.DATABASE_PATH) if c["client_id"] == s["client_id"]), {})
            project = client_record.get("project_name", "")
            note = client_record.get("reminder_note", "")

            self.tree.insert(
                "",
                "end",
                iid=s["client_id"],
                values=(status_str, s["name"], s["email"], s["company"], project, note, quota_str),
            )

    def _on_add_client(self):
        ClientEditDialog(self, client_data=None, on_save_callback=self._on_client_saved)

    def _on_edit_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select Client", "Please select a client from the table to edit.", parent=self)
            return
        client_id = selected[0]
        client_record = next((c for c in get_all_clients(Config.DATABASE_PATH) if c["client_id"] == client_id), None)
        if client_record:
            ClientEditDialog(self, client_data=client_record, on_save_callback=self._on_client_saved)

    def _on_toggle_active(self):
        selected = self.tree.selection()
        if not selected:
            return
        client_id = selected[0]
        client_record = next((c for c in get_all_clients(Config.DATABASE_PATH) if c["client_id"] == client_id), None)
        if client_record:
            client_record["is_active"] = 0 if client_record["is_active"] else 1
            upsert_client(client_record, Config.DATABASE_PATH)
            self._on_client_saved()

    def _on_sync_csv(self):
        count = sync_clients(Config.DATABASE_PATH, Config.CLIENTS_CSV_PATH, Config.CLIENTS_JSON_PATH)
        messagebox.showinfo("Sync Complete", f"Successfully synced {count} clients from CSV.", parent=self)
        self._on_client_saved()

    def _on_client_saved(self):
        self.reload_clients()
        self.app.dashboard_view.refresh_stats()

