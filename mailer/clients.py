"""
Client directory loader and synchronization.
Loads client records from user-friendly CSV or JSON files into SQLite.
"""

import csv
import json
from pathlib import Path
import re
from typing import Any, Dict, List

from mailer.database import upsert_client

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def is_valid_email(email: str) -> bool:
    """Validate standard email syntax."""
    if not email:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def create_sample_csv(csv_path: Path):
    """Generate a clean, user-friendly sample CSV file for up to 30 clients."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    sample_rows = [
        ["name", "email", "company", "project_name", "reminder_note", "daily_limit", "is_active"],
        ["John Doe", "john@clientcompany.com", "Apex Retail", "SEO & Content Marketing", "Review monthly performance report and approve draft copy.", "100", "1"],
        ["Sarah Jenkins", "sarah@nexustech.io", "Nexus Tech", "Google Ads Optimization", "Pending review of Q3 target keywords and bid adjustments.", "100", "1"],
        ["Michael Chang", "michael@lumencity.org", "Lumen City", "Brand Identity & Social", "Asset delivery scheduled for Friday review meeting.", "100", "1"],
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(sample_rows)


def load_from_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """Parse clients from CSV file."""
    if not csv_path.is_file():
        return []

    clients = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = row.get("email", "").strip()
            if not email or not is_valid_email(email):
                continue
            
            client_id = row.get("client_id", "").strip() or email.lower()
            name = row.get("name", "").strip() or email.split("@")[0].title()
            company = row.get("company", "").strip()
            project_name = row.get("project_name", "").strip() or "Marketing Campaign"
            reminder_note = row.get("reminder_note", "").strip() or "General work progress and milestone reminder."
            
            try:
                daily_limit = int(row.get("daily_limit", "100"))
            except ValueError:
                daily_limit = 100
                
            is_active_val = str(row.get("is_active", "1")).strip().lower()
            is_active = 1 if is_active_val in ("1", "true", "yes", "active") else 0

            clients.append({
                "client_id": client_id,
                "name": name,
                "email": email,
                "company": company,
                "project_name": project_name,
                "reminder_note": reminder_note,
                "daily_limit": daily_limit,
                "is_active": is_active
            })
    return clients


def load_from_json(json_path: Path) -> List[Dict[str, Any]]:
    """Parse clients from JSON file."""
    if not json_path.is_file():
        return []

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            raw_list = data if isinstance(data, list) else data.get("clients", [])
            
            clients = []
            for item in raw_list:
                email = item.get("email", "").strip()
                if not email or not is_valid_email(email):
                    continue
                clients.append({
                    "client_id": item.get("client_id", "").strip() or email.lower(),
                    "name": item.get("name", "").strip() or email.split("@")[0].title(),
                    "email": email,
                    "company": item.get("company", "").strip(),
                    "project_name": item.get("project_name", "").strip() or "Marketing Campaign",
                    "reminder_note": item.get("reminder_note", "").strip() or "General work progress reminder.",
                    "daily_limit": int(item.get("daily_limit", 100)),
                    "is_active": 1 if item.get("is_active", True) else 0
                })
            return clients
    except Exception:
        return []


def sync_clients(db_path: Path, csv_path: Path, json_path: Path) -> int:
    """
    Sync clients from CSV or JSON into the SQLite database.
    If neither file exists, creates a sample clients.csv file.
    Returns the number of clients synchronized.
    """
    clients = []
    
    # Priority: CSV first, then JSON
    if csv_path.is_file():
        clients = load_from_csv(csv_path)
    elif json_path.is_file():
        clients = load_from_json(json_path)
    else:
        # Create sample CSV
        create_sample_csv(csv_path)
        clients = load_from_csv(csv_path)

    for c in clients:
        upsert_client(c, db_path)

    return len(clients)

