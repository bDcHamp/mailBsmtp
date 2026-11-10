"""
Database management for Marketing SMTP Mailer.
Stores client registry and delivery history in a local SQLite database.
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
    """Initialize database tables if they do not exist."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
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
                        created_at REAL DEFAULT (strftime('%s', 'now')),
                        updated_at REAL DEFAULT (strftime('%s', 'now'))
                    )
                """)
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
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_delivery_window 
                    ON delivery_logs(client_id, status, sent_at)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_clients_active 
                    ON clients(is_active)
                """)
        finally:
            conn.close()


def upsert_client(client_data: Dict[str, Any], db_path: Path):
    """Insert or update client record."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                now = time.time()
                client_id = client_data.get("client_id") or client_data["email"].strip().lower()
                conn.execute("""
                    INSERT INTO clients (
                        client_id, name, email, company, project_name, 
                        reminder_note, daily_limit, is_active, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(client_id) DO UPDATE SET
                        name = excluded.name,
                        email = excluded.email,
                        company = excluded.company,
                        project_name = excluded.project_name,
                        reminder_note = excluded.reminder_note,
                        daily_limit = excluded.daily_limit,
                        is_active = excluded.is_active,
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
                    now
                ))
        finally:
            conn.close()


def get_active_clients(db_path: Path) -> List[Dict[str, Any]]:
    """Retrieve all active clients."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT client_id, name, email, company, project_name, 
                       reminder_note, daily_limit, is_active
                FROM clients
                WHERE is_active = 1
                ORDER BY id ASC
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


def get_all_clients(db_path: Path) -> List[Dict[str, Any]]:
    """Retrieve all clients including inactive ones."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT client_id, name, email, company, project_name, 
                       reminder_note, daily_limit, is_active
                FROM clients
                ORDER BY id ASC
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


def get_client_summary_stats(db_path: Path, window_hours: float = 24.0) -> List[Dict[str, Any]]:
    """Return aggregated status report for all clients."""
    clients = get_all_clients(db_path)
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

