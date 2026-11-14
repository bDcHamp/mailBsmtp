"""
Database management for Marketing SMTP Mailer.
Stores client registry, groups, email templates, and delivery history in a local SQLite database.
"""

from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

_DB_LOCK = threading.Lock()


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Create a connection with thread-safety and row factory enabled."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# -------------------------------------------------------------
# Default Starter Templates
# -------------------------------------------------------------

DEFAULT_STARTER_TEMPLATES = [
    {
        "name": "Template 1: Milestone Progress Review",
        "subject": "Work Progress & Action Items: {project_name}",
        "html_content": """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Work Progress Reminder</title>
</head>
<body style="font-family: Arial, sans-serif; background-color: #f8fafc; color: #1e293b; padding: 20px; line-height: 1.6;">
  <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px;">
    <h2 style="color: #2563eb; margin-top: 0;">Work Progress Reminder: {project_name}</h2>
    <p>Dear {client_name},</p>
    <p>This is a scheduled work update regarding your marketing deliverables with <strong>{company}</strong>.</p>
    <div style="background: #eff6ff; border-left: 4px solid #2563eb; padding: 14px; margin: 18px 0; border-radius: 4px;">
      <strong style="color: #1e40af;">Current Deliverable Milestone:</strong><br>
      {reminder_note}
    </div>
    <p style="font-size: 13px; color: #64748b;">
      Sequence #{sequence_num} of {daily_limit} &bull; Timestamp: {current_date} at {current_time}
    </p>
    <p style="margin-top: 24px;">Best regards,<br><strong>{sender_name}</strong></p>
  </div>
</body>
</html>""",
        "text_content": """Work Progress Reminder: {project_name}
Dear {client_name},

This is a scheduled work update regarding your marketing deliverables with {company}.

Current Deliverable Milestone:
{reminder_note}

Sequence #{sequence_num} of {daily_limit} • Timestamp: {current_date} at {current_time}
Best regards,
{sender_name}"""
    },
    {
        "name": "Template 2: Quick Deliverables Check-in",
        "subject": "Quick Follow-Up: Reviewing Deliverables for {project_name}",
        "html_content": """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Deliverables Check-in</title>
</head>
<body style="font-family: Arial, sans-serif; background-color: #f8fafc; color: #1e293b; padding: 20px; line-height: 1.6;">
  <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px;">
    <h2 style="color: #059669; margin-top: 0;">Campaign Status Check-in</h2>
    <p>Hi {client_name},</p>
    <p>We are actively optimizing campaign assets for <strong>{project_name}</strong> at <strong>{company}</strong>.</p>
    <div style="background: #ecfdf5; border-left: 4px solid #059669; padding: 14px; margin: 18px 0; border-radius: 4px;">
      <strong style="color: #065f46;">Action Required / Current Focus:</strong><br>
      {reminder_note}
    </div>
    <p>Please review the current deliverable and let us know if any adjustments are needed before we proceed to the next phase.</p>
    <p style="font-size: 13px; color: #64748b;">
      Update #{sequence_num} &bull; Scheduled dispatch: {current_date}
    </p>
    <p style="margin-top: 24px;">Kind regards,<br><strong>{sender_name}</strong></p>
  </div>
</body>
</html>""",
        "text_content": """Campaign Status Check-in
Hi {client_name},

We are actively optimizing campaign assets for {project_name} at {company}.

Action Required / Current Focus:
{reminder_note}

Please review the current deliverable and let us know if any adjustments are needed before we proceed to the next phase.

Update #{sequence_num} • Scheduled dispatch: {current_date}
Kind regards,
{sender_name}"""
    },
    {
        "name": "Template 3: Action Items & Milestone Sign-off",
        "subject": "Action Items & Timeline Review for {project_name} - {company}",
        "html_content": """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Action Items Review</title>
</head>
<body style="font-family: Arial, sans-serif; background-color: #f8fafc; color: #1e293b; padding: 20px; line-height: 1.6;">
  <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px;">
    <h2 style="color: #7c3aed; margin-top: 0;">Weekly Milestone & Action Items</h2>
    <p>Hello {client_name},</p>
    <p>Here is your latest scheduled status notification for <strong>{project_name}</strong>.</p>
    <div style="background: #f5f3ff; border-left: 4px solid #7c3aed; padding: 14px; margin: 18px 0; border-radius: 4px;">
      <strong style="color: #5b21b6;">Deliverable Priority:</strong><br>
      {reminder_note}
    </div>
    <p>Our team is available if you have questions or require strategic changes.</p>
    <p style="font-size: 13px; color: #64748b;">
      Sequence #{sequence_num} of {daily_limit} &bull; Generated: {current_date} {current_time}
    </p>
    <p style="margin-top: 24px;">Warm regards,<br><strong>{sender_name}</strong></p>
  </div>
</body>
</html>""",
        "text_content": """Weekly Milestone & Action Items
Hello {client_name},

Here is your latest scheduled status notification for {project_name}.

Deliverable Priority:
{reminder_note}

Our team is available if you have questions or require strategic changes.

Sequence #{sequence_num} of {daily_limit} • Generated: {current_date} {current_time}
Warm regards,
{sender_name}"""
    }
]


def init_db(db_path: Path):
    """Initialize database tables and run lightweight migrations if needed."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                # 1. Create groups table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS groups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT DEFAULT '',
                        is_active INTEGER DEFAULT 1,
                        created_at REAL DEFAULT (strftime('%s', 'now'))
                    )
                """)

                # 2. Create clients table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS clients (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        client_id TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        email TEXT NOT NULL,
                        company TEXT DEFAULT '',
                        project_name TEXT DEFAULT '',
                        reminder_note TEXT DEFAULT '',
                        daily_limit INTEGER DEFAULT 100,
                        is_active INTEGER DEFAULT 1,
                        group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL,
                        rotation_interval_minutes INTEGER DEFAULT 0,
                        created_at REAL DEFAULT (strftime('%s', 'now')),
                        updated_at REAL DEFAULT (strftime('%s', 'now'))
                    )
                """)

                # Check if columns exist in clients table
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(clients)")
                client_cols = [row["name"] for row in cursor.fetchall()]
                if "group_id" not in client_cols:
                    conn.execute("ALTER TABLE clients ADD COLUMN group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL")
                if "rotation_interval_minutes" not in client_cols:
                    conn.execute("ALTER TABLE clients ADD COLUMN rotation_interval_minutes INTEGER DEFAULT 0")

                # 3. Create email_templates table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS email_templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        subject TEXT NOT NULL,
                        html_content TEXT NOT NULL,
                        text_content TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        created_at REAL DEFAULT (strftime('%s', 'now')),
                        updated_at REAL DEFAULT (strftime('%s', 'now'))
                    )
                """)

                # 4. Create client_templates junction table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS client_templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        client_id TEXT NOT NULL,
                        template_id INTEGER NOT NULL REFERENCES email_templates(id) ON DELETE CASCADE,
                        created_at REAL DEFAULT (strftime('%s', 'now')),
                        UNIQUE(client_id, template_id)
                    )
                """)

                # 5. Create delivery_logs table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS delivery_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        client_id TEXT NOT NULL,
                        recipient_email TEXT NOT NULL,
                        subject TEXT,
                        sequence_num INTEGER DEFAULT 1,
                        status TEXT NOT NULL, -- 'SUCCESS' or 'FAILED'
                        error_message TEXT,
                        template_id INTEGER,
                        template_name TEXT,
                        sent_at REAL NOT NULL
                    )
                """)

                # Check if template columns exist in delivery_logs
                cursor.execute("PRAGMA table_info(delivery_logs)")
                log_cols = [row["name"] for row in cursor.fetchall()]
                if "template_id" not in log_cols:
                    conn.execute("ALTER TABLE delivery_logs ADD COLUMN template_id INTEGER")
                if "template_name" not in log_cols:
                    conn.execute("ALTER TABLE delivery_logs ADD COLUMN template_name TEXT")

                # Indexes
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_delivery_window 
                    ON delivery_logs(client_id, status, sent_at)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_clients_active 
                    ON clients(is_active)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_clients_group 
                    ON clients(group_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_client_templates_cid 
                    ON client_templates(client_id)
                """)

                # Auto-seed starter templates if email_templates is empty
                cursor.execute("SELECT COUNT(*) FROM email_templates")
                if cursor.fetchone()[0] == 0:
                    now = time.time()
                    for t in DEFAULT_STARTER_TEMPLATES:
                        conn.execute("""
                            INSERT INTO email_templates (name, subject, html_content, text_content, is_active, created_at, updated_at)
                            VALUES (?, ?, ?, ?, 1, ?, ?)
                        """, (t["name"], t["subject"], t["html_content"], t["text_content"], now, now))
        finally:
            conn.close()


# -------------------------------------------------------------
# Groups CRUD
# -------------------------------------------------------------

def create_group(name: str, description: str, db_path: Path) -> int:
    """Create a new client group."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO groups (name, description, is_active, created_at)
                    VALUES (?, ?, 1, ?)
                """, (name.strip(), description.strip(), time.time()))
                return cursor.lastrowid
        finally:
            conn.close()


def get_all_groups(db_path: Path) -> List[Dict[str, Any]]:
    """Retrieve all groups with client counts and active counts."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT g.id, g.name, g.description, g.is_active, g.created_at,
                       COUNT(c.id) AS client_count,
                       COALESCE(SUM(CASE WHEN c.is_active = 1 THEN 1 ELSE 0 END), 0) AS active_client_count
                FROM groups g
                LEFT JOIN clients c ON c.group_id = g.id
                GROUP BY g.id
                ORDER BY g.id ASC
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


def get_group(group_id: int, db_path: Path) -> Optional[Dict[str, Any]]:
    """Retrieve a single group by ID."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM groups WHERE id = ?", (group_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def update_group(group_id: int, name: str, description: str, db_path: Path) -> bool:
    """Update a group's name and description."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                conn.execute("""
                    UPDATE groups SET name = ?, description = ? WHERE id = ?
                """, (name.strip(), description.strip(), group_id))
                return True
        finally:
            conn.close()


def toggle_group_active(group_id: int, db_path: Path) -> bool:
    """Toggle group active state AND synchronize all clients in this group."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT is_active FROM groups WHERE id = ?", (group_id,))
                row = cursor.fetchone()
                if not row:
                    return False
                new_state = 0 if row["is_active"] else 1
                conn.execute("UPDATE groups SET is_active = ? WHERE id = ?", (new_state, group_id))
                conn.execute("UPDATE clients SET is_active = ? WHERE group_id = ?", (new_state, group_id))
                return bool(new_state)
        finally:
            conn.close()


def delete_group(group_id: int, delete_clients: bool, db_path: Path) -> bool:
    """Delete a group. If delete_clients is True, permanently deletes clients inside."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                cursor = conn.cursor()
                if delete_clients:
                    cursor.execute("SELECT client_id FROM clients WHERE group_id = ?", (group_id,))
                    cids = [r["client_id"] for r in cursor.fetchall()]
                    for cid in cids:
                        conn.execute("DELETE FROM delivery_logs WHERE client_id = ?", (cid,))
                        conn.execute("DELETE FROM client_templates WHERE client_id = ?", (cid,))
                    conn.execute("DELETE FROM clients WHERE group_id = ?", (group_id,))
                else:
                    conn.execute("UPDATE clients SET group_id = NULL WHERE group_id = ?", (group_id,))
                conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
                return True
        finally:
            conn.close()


# -------------------------------------------------------------
# Email Templates CRUD
# -------------------------------------------------------------

def create_email_template(
    name: str,
    subject: str,
    html_content: str,
    text_content: str,
    is_active: int = 1,
    db_path: Path = None,
) -> int:
    """Create a new email template."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                now = time.time()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO email_templates (name, subject, html_content, text_content, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (name.strip(), subject.strip(), html_content, text_content, int(is_active), now, now))
                return cursor.lastrowid
        finally:
            conn.close()


def get_all_templates(db_path: Path) -> List[Dict[str, Any]]:
    """Retrieve all email templates with counts of assigned clients."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.id, t.name, t.subject, t.html_content, t.text_content, t.is_active,
                       t.created_at, t.updated_at,
                       COUNT(ct.client_id) AS assigned_clients_count
                FROM email_templates t
                LEFT JOIN client_templates ct ON ct.template_id = t.id
                GROUP BY t.id
                ORDER BY t.id ASC
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


def get_template_by_id(template_id: int, db_path: Path) -> Optional[Dict[str, Any]]:
    """Retrieve a single email template by ID."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM email_templates WHERE id = ?", (template_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def update_email_template(
    template_id: int,
    name: str,
    subject: str,
    html_content: str,
    text_content: str,
    is_active: int,
    db_path: Path,
) -> bool:
    """Update template fields."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                conn.execute("""
                    UPDATE email_templates
                    SET name = ?, subject = ?, html_content = ?, text_content = ?, is_active = ?, updated_at = ?
                    WHERE id = ?
                """, (name.strip(), subject.strip(), html_content, text_content, int(is_active), time.time(), template_id))
                return True
        finally:
            conn.close()


def toggle_template_active(template_id: int, db_path: Path) -> bool:
    """Toggle active status of a template."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT is_active FROM email_templates WHERE id = ?", (template_id,))
                row = cursor.fetchone()
                if not row:
                    return False
                new_state = 0 if row["is_active"] else 1
                conn.execute("UPDATE email_templates SET is_active = ?, updated_at = ? WHERE id = ?", (new_state, time.time(), template_id))
                return bool(new_state)
        finally:
            conn.close()


def duplicate_email_template(template_id: int, db_path: Path) -> Optional[int]:
    """Clone an existing template with a new name."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM email_templates WHERE id = ?", (template_id,))
                orig = cursor.fetchone()
                if not orig:
                    return None
                
                new_name = f"{orig['name']} (Copy)"
                # Ensure unique name
                counter = 1
                while True:
                    cursor.execute("SELECT id FROM email_templates WHERE name = ?", (new_name,))
                    if not cursor.fetchone():
                        break
                    counter += 1
                    new_name = f"{orig['name']} (Copy {counter})"

                now = time.time()
                cursor.execute("""
                    INSERT INTO email_templates (name, subject, html_content, text_content, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (new_name, orig["subject"], orig["html_content"], orig["text_content"], orig["is_active"], now, now))
                return cursor.lastrowid
        finally:
            conn.close()


def delete_email_template(template_id: int, db_path: Path) -> bool:
    """Delete a template and remove its associations in client_templates."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                conn.execute("DELETE FROM client_templates WHERE template_id = ?", (template_id,))
                cursor = conn.cursor()
                cursor.execute("DELETE FROM email_templates WHERE id = ?", (template_id,))
                return cursor.rowcount > 0
        finally:
            conn.close()


# -------------------------------------------------------------
# Client-Template Association & Auto-Rotation Engine
# -------------------------------------------------------------

def get_client_assigned_templates(client_id: str, db_path: Path) -> List[Dict[str, Any]]:
    """Retrieve templates explicitly assigned to a client."""
    cid = client_id.strip().lower()
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.id, t.name, t.subject, t.is_active
                FROM email_templates t
                INNER JOIN client_templates ct ON ct.template_id = t.id
                WHERE ct.client_id = ?
                ORDER BY t.id ASC
            """, (cid,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


def get_client_assigned_template_ids(client_id: str, db_path: Path) -> List[int]:
    """Return list of template IDs assigned to a client."""
    cid = client_id.strip().lower()
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT template_id FROM client_templates WHERE client_id = ?", (cid,))
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()


def set_client_assigned_templates(client_id: str, template_ids: List[int], db_path: Path):
    """Set the list of templates assigned to a client (replaces previous assignment)."""
    cid = client_id.strip().lower()
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                conn.execute("DELETE FROM client_templates WHERE client_id = ?", (cid,))
                for tid in template_ids:
                    try:
                        valid_tid = int(tid)
                        conn.execute("""
                            INSERT OR IGNORE INTO client_templates (client_id, template_id, created_at)
                            VALUES (?, ?, ?)
                        """, (cid, valid_tid, time.time()))
                    except (ValueError, TypeError):
                        pass
        finally:
            conn.close()


def get_next_template_for_client(client_id: str, db_path: Path) -> Optional[Dict[str, Any]]:
    """
    Select the next rotating template for a client.
    Guarantees that consecutive emails do not reuse the same template.
    Honors:
      1. User-selected templates for this specific client (from client_templates).
      2. If none explicitly assigned, falls back to all active templates.
      3. Rotation timing: rotation_interval_minutes (0 = rotate every send, >0 = rotate after X minutes).
    """
    cid = client_id.strip().lower()
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()

            # 1. Fetch client rotation settings
            cursor.execute("SELECT rotation_interval_minutes FROM clients WHERE client_id = ?", (cid,))
            crow = cursor.fetchone()
            rotation_interval = crow["rotation_interval_minutes"] if crow and crow["rotation_interval_minutes"] is not None else 0

            # 2. Get assigned active templates for this client
            cursor.execute("""
                SELECT t.id, t.name, t.subject, t.html_content, t.text_content, t.is_active
                FROM email_templates t
                INNER JOIN client_templates ct ON ct.template_id = t.id
                WHERE ct.client_id = ? AND t.is_active = 1
                ORDER BY t.id ASC
            """, (cid,))
            eligible = [dict(row) for row in cursor.fetchall()]

            # 3. If no templates explicitly assigned, fallback to all active templates
            if not eligible:
                cursor.execute("""
                    SELECT id, name, subject, html_content, text_content, is_active
                    FROM email_templates
                    WHERE is_active = 1
                    ORDER BY id ASC
                """)
                eligible = [dict(row) for row in cursor.fetchall()]

            if not eligible:
                return None

            if len(eligible) == 1:
                return eligible[0]

            # 4. Check the last successful send for this client to determine next in rotation
            cursor.execute("""
                SELECT template_id, sent_at
                FROM delivery_logs
                WHERE client_id = ? AND status = 'SUCCESS' AND template_id IS NOT NULL
                ORDER BY sent_at DESC LIMIT 1
            """, (cid,))
            last_send = cursor.fetchone()

            if not last_send:
                return eligible[0]

            last_tid = last_send["template_id"]
            last_sent = last_send["sent_at"]

            # If user configured a time window before rotating (e.g. keep same template for X minutes):
            if rotation_interval > 0:
                elapsed_minutes = (time.time() - last_sent) / 60.0
                if elapsed_minutes < rotation_interval:
                    # Still within time window, reuse last template if it is in eligible
                    match = next((t for t in eligible if t["id"] == last_tid), None)
                    if match:
                        return match

            # Rotate to next template in the list (round-robin)
            matched_indices = [i for i, t in enumerate(eligible) if t["id"] == last_tid]
            if matched_indices:
                next_index = (matched_indices[0] + 1) % len(eligible)
                return eligible[next_index]
            else:
                return eligible[0]

        finally:
            conn.close()


# -------------------------------------------------------------
# Clients Operations
# -------------------------------------------------------------

def upsert_client(client_data: Dict[str, Any], db_path: Path):
    """Insert or update client record and optional assigned template IDs."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                now = time.time()
                client_id = client_data.get("client_id") or client_data["email"].strip().lower()
                group_id = client_data.get("group_id")
                if group_id in ("", None, "null", "None"):
                    group_id = None
                else:
                    try:
                        group_id = int(group_id)
                    except (ValueError, TypeError):
                        group_id = None

                rot_interval = client_data.get("rotation_interval_minutes", 0)
                try:
                    rot_interval = int(rot_interval)
                except (ValueError, TypeError):
                    rot_interval = 0

                conn.execute("""
                    INSERT INTO clients (
                        client_id, name, email, company, project_name, 
                        reminder_note, daily_limit, is_active, group_id, rotation_interval_minutes, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(client_id) DO UPDATE SET
                        name = excluded.name,
                        email = excluded.email,
                        company = excluded.company,
                        project_name = excluded.project_name,
                        reminder_note = excluded.reminder_note,
                        daily_limit = excluded.daily_limit,
                        is_active = excluded.is_active,
                        group_id = COALESCE(excluded.group_id, clients.group_id),
                        rotation_interval_minutes = excluded.rotation_interval_minutes,
                        updated_at = excluded.updated_at
                """, (
                    client_id,
                    client_data.get("name", "").strip(),
                    client_data["email"].strip().lower(),
                    client_data.get("company", "").strip(),
                    client_data.get("project_name", "").strip(),
                    client_data.get("reminder_note", "").strip(),
                    int(client_data.get("daily_limit", 100)),
                    int(client_data.get("is_active", 1)),
                    group_id,
                    rot_interval,
                    now
                ))

                # Handle template assignments if provided
                if "template_ids" in client_data:
                    tids = client_data["template_ids"]
                    conn.execute("DELETE FROM client_templates WHERE client_id = ?", (client_id,))
                    if tids:
                        for tid in tids:
                            try:
                                conn.execute("""
                                    INSERT OR IGNORE INTO client_templates (client_id, template_id, created_at)
                                    VALUES (?, ?, ?)
                                """, (client_id, int(tid), now))
                            except (ValueError, TypeError):
                                pass
        finally:
            conn.close()


def delete_client(client_id: str, db_path: Path) -> bool:
    """Permanently delete a client, their template mappings, and their delivery logs."""
    cid = client_id.strip().lower()
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM clients WHERE client_id = ?", (cid,))
                conn.execute("DELETE FROM delivery_logs WHERE client_id = ?", (cid,))
                conn.execute("DELETE FROM client_templates WHERE client_id = ?", (cid,))
                return cursor.rowcount > 0
        finally:
            conn.close()


def get_active_clients(db_path: Path) -> List[Dict[str, Any]]:
    """
    Retrieve all active clients.
    Critically, if a client belongs to a group, that group MUST also be active.
    """
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.client_id, c.name, c.email, c.company, c.project_name, 
                       c.reminder_note, c.daily_limit, c.is_active, c.group_id,
                       c.rotation_interval_minutes,
                       g.name AS group_name
                FROM clients c
                LEFT JOIN groups g ON c.group_id = g.id
                WHERE c.is_active = 1 AND (c.group_id IS NULL OR g.is_active = 1)
                ORDER BY c.id ASC
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


def get_all_clients(db_path: Path, group_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retrieve all clients including inactive ones, optionally filtered by group_id."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            if group_id is not None:
                cursor.execute("""
                    SELECT c.client_id, c.name, c.email, c.company, c.project_name, 
                           c.reminder_note, c.daily_limit, c.is_active, c.group_id,
                           c.rotation_interval_minutes,
                           g.name AS group_name, g.is_active AS group_is_active
                    FROM clients c
                    LEFT JOIN groups g ON c.group_id = g.id
                    WHERE c.group_id = ?
                    ORDER BY c.id ASC
                """, (group_id,))
            else:
                cursor.execute("""
                    SELECT c.client_id, c.name, c.email, c.company, c.project_name, 
                           c.reminder_note, c.daily_limit, c.is_active, c.group_id,
                           c.rotation_interval_minutes,
                           g.name AS group_name, g.is_active AS group_is_active
                    FROM clients c
                    LEFT JOIN groups g ON c.group_id = g.id
                    ORDER BY c.id ASC
                """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


def get_client_sends_in_window(client_id: str, window_hours: float, db_path: Path) -> int:
    """Return count of successful emails sent to this client within rolling window."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cutoff = time.time() - (window_hours * 3600.0)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM delivery_logs
                WHERE client_id = ? AND status = 'SUCCESS' AND sent_at >= ?
            """, (client_id, cutoff))
            return cursor.fetchone()[0]
        finally:
            conn.close()


def get_client_last_sent_time(client_id: str, db_path: Path) -> Optional[float]:
    """Return UNIX timestamp of the last successful email sent to this client."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(sent_at) FROM delivery_logs
                WHERE client_id = ? AND status = 'SUCCESS'
            """, (client_id,))
            res = cursor.fetchone()[0]
            return float(res) if res is not None else None
        finally:
            conn.close()


def record_delivery(
    client_id: str,
    recipient_email: str,
    subject: str,
    sequence_num: int,
    status: str,
    error_message: Optional[str],
    db_path: Path,
    template_id: Optional[int] = None,
    template_name: Optional[str] = None,
):
    """Log an email delivery attempt into delivery_logs with optional template metadata."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                conn.execute("""
                    INSERT INTO delivery_logs (
                        client_id, recipient_email, subject, 
                        sequence_num, status, error_message, template_id, template_name, sent_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    client_id,
                    recipient_email,
                    subject,
                    sequence_num,
                    status.upper(),
                    error_message or "",
                    template_id,
                    template_name,
                    time.time()
                ))
        finally:
            conn.close()


def get_client_summary_stats(db_path: Path, window_hours: float = 24.0, group_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return aggregated status report for clients, optionally filtered by group_id."""
    clients = get_all_clients(db_path, group_id=group_id)
    stats = []
    now = time.time()
    cutoff = now - (window_hours * 3600.0)

    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            for client in clients:
                cid = client["client_id"]
                # Count successful in 24h
                cursor.execute("""
                    SELECT COUNT(*), MAX(sent_at) FROM delivery_logs
                    WHERE client_id = ? AND status = 'SUCCESS' AND sent_at >= ?
                """, (cid, cutoff))
                row = cursor.fetchone()
                sent_24h = row[0] if row else 0
                last_sent = row[1] if row and row[1] is not None else None

                # Count failures in 24h
                cursor.execute("""
                    SELECT COUNT(*) FROM delivery_logs
                    WHERE client_id = ? AND status = 'FAILED' AND sent_at >= ?
                """, (cid, cutoff))
                fail_row = cursor.fetchone()
                failed_24h = fail_row[0] if fail_row else 0

                limit = client["daily_limit"]
                remaining = max(0, limit - sent_24h)

                # Fetch assigned template IDs
                cursor.execute("SELECT template_id FROM client_templates WHERE client_id = ?", (cid,))
                assigned_tids = [r[0] for r in cursor.fetchall()]

                stats.append({
                    "client_id": cid,
                    "name": client["name"],
                    "email": client["email"],
                    "company": client["company"],
                    "project_name": client.get("project_name", ""),
                    "reminder_note": client.get("reminder_note", ""),
                    "group_id": client.get("group_id"),
                    "group_name": client.get("group_name"),
                    "group_is_active": client.get("group_is_active", 1),
                    "rotation_interval_minutes": client.get("rotation_interval_minutes", 0),
                    "assigned_template_ids": assigned_tids,
                    "is_active": bool(client["is_active"]),
                    "daily_limit": limit,
                    "sent_24h": sent_24h,
                    "failed_24h": failed_24h,
                    "remaining_quota": remaining,
                    "last_sent": last_sent,
                })
        finally:
            conn.close()

    return stats
