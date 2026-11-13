"""
Database management for Marketing SMTP Mailer.
Stores client registry, groups, and delivery history in a local SQLite database.
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
                        created_at REAL DEFAULT (strftime('%s', 'now')),
                        updated_at REAL DEFAULT (strftime('%s', 'now'))
                    )
                """)

                # Check if group_id exists in clients table (migration for existing DB)
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(clients)")
                cols = [row["name"] for row in cursor.fetchall()]
                if "group_id" not in cols:
                    conn.execute("ALTER TABLE clients ADD COLUMN group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL")

                # 3. Create delivery_logs table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS delivery_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        client_id TEXT NOT NULL,
                        recipient_email TEXT NOT NULL,
                        subject TEXT,
                        sequence_num INTEGER DEFAULT 1,
                        status TEXT NOT NULL, -- 'SUCCESS' or 'FAILED'
                        error_message TEXT,
                        sent_at REAL NOT NULL
                    )
                """)

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
                # Sync client active flags to match group status
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
                    conn.execute("DELETE FROM clients WHERE group_id = ?", (group_id,))
                else:
                    conn.execute("UPDATE clients SET group_id = NULL WHERE group_id = ?", (group_id,))
                conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
                return True
        finally:
            conn.close()


# -------------------------------------------------------------
# Clients Operations
# -------------------------------------------------------------

def upsert_client(client_data: Dict[str, Any], db_path: Path):
    """Insert or update client record."""
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

                conn.execute("""
                    INSERT INTO clients (
                        client_id, name, email, company, project_name, 
                        reminder_note, daily_limit, is_active, group_id, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(client_id) DO UPDATE SET
                        name = excluded.name,
                        email = excluded.email,
                        company = excluded.company,
                        project_name = excluded.project_name,
                        reminder_note = excluded.reminder_note,
                        daily_limit = excluded.daily_limit,
                        is_active = excluded.is_active,
                        group_id = COALESCE(excluded.group_id, clients.group_id),
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
                    now
                ))
        finally:
            conn.close()


def delete_client(client_id: str, db_path: Path) -> bool:
    """Permanently delete a client and their delivery logs."""
    cid = client_id.strip().lower()
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM clients WHERE client_id = ?", (cid,))
                conn.execute("DELETE FROM delivery_logs WHERE client_id = ?", (cid,))
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
    db_path: Path
):
    """Log an email delivery attempt into delivery_logs."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                conn.execute("""
                    INSERT INTO delivery_logs (
                        client_id, recipient_email, subject, 
                        sequence_num, status, error_message, sent_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    client_id,
                    recipient_email,
                    subject,
                    sequence_num,
                    status.upper(),
                    error_message or "",
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
