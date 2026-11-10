"""
Automated unit tests for Marketing SMTP Work Reminder System.
Tests database quota tracking, template rendering, and client CSV loading.
"""

from email.message import Message
from pathlib import Path
import tempfile
import time
import unittest

from mailer.clients import load_from_csv, sync_clients
from mailer.config import Config
from mailer.database import (
    get_active_clients,
    get_client_last_sent_time,
    get_client_sends_in_window,
    get_client_summary_stats,
    init_db,
    record_delivery,
    upsert_client,
)
from mailer.engine import DispatchEngine
from mailer.templates import create_reminder_message, render_string


class TestMarketingMailer(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        self.db_path = self.test_dir / "test_mailer.db"
        self.csv_path = self.test_dir / "test_clients.csv"
        self.json_path = self.test_dir / "test_clients.json"
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_database_initialization_and_upsert(self):
        client_data = {
            "client_id": "client1@example.com",
            "name": "Jane Smith",
            "email": "client1@example.com",
            "company": "Smith Retail",
            "project_name": "SEO Optimization",
            "reminder_note": "Quarterly review meeting scheduled.",
            "daily_limit": 100,
            "is_active": 1,
        }
        upsert_client(client_data, self.db_path)
        active = get_active_clients(self.db_path)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["name"], "Jane Smith")
        self.assertEqual(active[0]["daily_limit"], 100)

    def test_rolling_24_hour_quota_enforcement(self):
        client_id = "test@company.com"
        now = time.time()

        # Record 50 deliveries in the last 2 hours
        for i in range(50):
            record_delivery(
                client_id=client_id,
                recipient_email=client_id,
                subject=f"Work Reminder #{i+1}",
                sequence_num=i + 1,
                status="SUCCESS",
                error_message=None,
                db_path=self.db_path,
            )

        # Count in 24h window should be exactly 50
        count = get_client_sends_in_window(client_id, 24.0, self.db_path)
        self.assertEqual(count, 50)

        # Record 50 more deliveries -> total 100
        for i in range(50, 100):
            record_delivery(
                client_id=client_id,
                recipient_email=client_id,
                subject=f"Work Reminder #{i+1}",
                sequence_num=i + 1,
                status="SUCCESS",
                error_message=None,
                db_path=self.db_path,
            )

        count = get_client_sends_in_window(client_id, 24.0, self.db_path)
        self.assertEqual(count, 100)

        # Check engine: client should NOT be due when quota of 100 is reached
        class MockConfig(Config):
            DATABASE_PATH = self.db_path
            DAILY_CAP_PER_CLIENT = 100
            WINDOW_HOURS = 24.0
            MIN_INTERVAL_SECONDS = 0.0

        engine = DispatchEngine(MockConfig)
        client = {
            "client_id": client_id,
            "email": client_id,
            "daily_limit": 100,
        }
        self.assertFalse(engine.is_client_due(client, now=time.time()))

    def test_pacing_interval_prevents_burst(self):
        client_id = "pacing@company.com"
        # Record 1 send right now
        record_delivery(
            client_id=client_id,
            recipient_email=client_id,
            subject="Work Reminder #1",
            sequence_num=1,
            status="SUCCESS",
            error_message=None,
            db_path=self.db_path,
        )

        class MockConfig(Config):
            DATABASE_PATH = self.db_path
            DAILY_CAP_PER_CLIENT = 100
            WINDOW_HOURS = 24.0
            MIN_INTERVAL_SECONDS = 600.0  # 10 minutes pacing

        engine = DispatchEngine(MockConfig)
        client = {
            "client_id": client_id,
            "email": client_id,
            "daily_limit": 100,
        }

        # Immediately after sending, client should NOT be due
        self.assertFalse(engine.is_client_due(client, now=time.time()))

        # After 11 minutes (660s), client SHOULD be due
        future_time = time.time() + 660.0
        self.assertTrue(engine.is_client_due(client, now=future_time))

    def test_csv_sync(self):
        csv_content = """name,email,company,project_name,reminder_note,daily_limit,is_active
Alpha Client,alpha@domain.com,Alpha Corp,Search Ads,Check ad copy,100,1
Beta Client,beta@domain.com,Beta LLC,Social Growth,Approve graphics,100,1
"""
        self.csv_path.write_text(csv_content, encoding="utf-8")
        synced_count = sync_clients(self.db_path, self.csv_path, self.json_path)
        self.assertEqual(synced_count, 2)

        clients = get_active_clients(self.db_path)
        self.assertEqual(len(clients), 2)
        self.assertEqual(clients[0]["name"], "Alpha Client")
        self.assertEqual(clients[1]["name"], "Beta Client")

    def test_template_rendering_and_rfc_headers(self):
        client = {
            "name": "Jane Marketing",
            "email": "jane@partner.org",
            "company": "Partner Org",
            "project_name": "Rebranding 2026",
            "reminder_note": "Deliverable check: Color palette signed off.",
            "daily_limit": 100,
        }
        msg = create_reminder_message(
            client=client,
            sequence_num=1,
            sender_name="Agency Team",
            sender_email="team@agency.com",
            subject_prefix="Client Action Reminder",
            html_template_path=Path("templates/reminder.html"),
            text_template_path=Path("templates/reminder.txt"),
        )

        self.assertIn("Client Action Reminder", msg["Subject"])
        self.assertIn("Rebranding 2026", msg["Subject"])
        self.assertIn("jane@partner.org", msg["To"])
        self.assertIn("team@agency.com", msg["From"])
        self.assertIsNotNone(msg["Message-ID"])
        self.assertIsNotNone(msg["Date"])
        self.assertEqual(msg["Precedence"], "bulk")


if __name__ == "__main__":
    unittest.main()

