"""
Automated unit and integration tests for Marketing Mailer Web Version.
"""

import io
import os
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import unittest

from mailer.config import Config
from mailer.database import get_active_clients, get_all_clients, get_all_groups, init_db
from web.app import create_app
from web.engine_service import engine_manager


class TestWebMailer(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        self.test_db = self.test_dir / "test_web.db"
        init_db(self.test_db)

        # Configure test environment
        Config.DATABASE_PATH = self.test_db
        os.environ["WEB_ADMIN_USER"] = "testadmin"
        os.environ["WEB_ADMIN_PASSWORD"] = "testpass123"

        # Mock SMTP client so tests don't attempt external network connections
        self.smtp_patch = patch("mailer.smtp_client.SMTPClient.test_connection", return_value=(True, "Mock Connected"))
        self.smtp_patch.start()
        self.smtp_send_patch = patch("mailer.smtp_client.SMTPClient.send_email", return_value=(True, None))
        self.smtp_send_patch.start()

        self.app = create_app({"TESTING": True, "SECRET_KEY": "test-secret"})
        self.client = self.app.test_client()

    def tearDown(self):
        if engine_manager.is_running:
            engine_manager.stop()
        self.smtp_send_patch.stop()
        self.smtp_patch.stop()
        self.temp_dir.cleanup()

    def test_unauthenticated_redirect(self):
        """Unauthenticated access to dashboard should redirect to login."""
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_login_failure(self):
        """Wrong credentials should stay on login page with error."""
        response = self.client.post("/login", data={
            "username": "testadmin",
            "password": "wrongpassword"
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid username or password", response.data)

    def test_login_success(self):
        """Correct credentials should set session and redirect to dashboard."""
        response = self.client.post("/login", data={
            "username": "testadmin",
            "password": "testpass123"
        }, follow_redirects=False)
        self.assertEqual(response.status_code, 302)

        # Follow into dashboard
        with self.client:
            dash_resp = self.client.get("/")
            self.assertEqual(dash_resp.status_code, 200)
            self.assertIn(b"Dashboard", dash_resp.data)

    def test_api_unauthorized(self):
        """Unauthenticated API requests should return 401."""
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertFalse(data["success"])

    def test_authenticated_api_stats_and_client_crud(self):
        """Verify API stats, adding clients, and toggling active status."""
        # Log in
        self.client.post("/login", data={"username": "testadmin", "password": "testpass123"})

        # Stats check
        stats_resp = self.client.get("/api/stats")
        self.assertEqual(stats_resp.status_code, 200)
        stats = stats_resp.get_json()
        self.assertIn("active_clients", stats)
        self.assertIn("is_running", stats)
        self.assertIn("total_groups", stats)

        # Add a client via API
        new_client = {
            "name": "Web Test Client",
            "email": "webtest@example.com",
            "company": "Contabo Corp",
            "project_name": "Cloud SEO",
            "reminder_note": "Server migration review.",
            "daily_limit": 100,
            "is_active": 1,
        }
        add_resp = self.client.post("/api/clients/add", json=new_client)
        self.assertEqual(add_resp.status_code, 200)
        self.assertTrue(add_resp.get_json()["success"])

        # Check in DB
        clients = get_all_clients(self.test_db)
        match = next((c for c in clients if c["email"] == "webtest@example.com"), None)
        self.assertIsNotNone(match)
        self.assertEqual(match["company"], "Contabo Corp")

        # Toggle client active
        toggle_resp = self.client.post("/api/clients/toggle-active", json={"client_id": "webtest@example.com"})
        self.assertEqual(toggle_resp.status_code, 200)
        self.assertFalse(toggle_resp.get_json()["is_active"])

    def test_client_delete(self):
        """Verify deleting a client removes them from SQLite."""
        self.client.post("/login", data={"username": "testadmin", "password": "testpass123"})
        initial_count = len(get_all_clients(self.test_db))

        # Add client
        self.client.post("/api/clients/add", json={
            "name": "To Delete",
            "email": "delete_me@example.com"
        })
        self.assertEqual(len(get_all_clients(self.test_db)), initial_count + 1)

        # Delete client
        del_resp = self.client.post("/api/clients/delete", json={"client_id": "delete_me@example.com"})
        self.assertEqual(del_resp.status_code, 200)
        self.assertTrue(del_resp.get_json()["success"])

        # Confirm gone
        self.assertEqual(len(get_all_clients(self.test_db)), initial_count)

    def test_groups_crud_and_turn_off_feature(self):
        """
        Verify creating groups, assigning clients, and turning off a group
        so that active reminders are stopped for that group.
        """
        self.client.post("/login", data={"username": "testadmin", "password": "testpass123"})
        initial_active = len(get_active_clients(self.test_db))

        # 1. Create a group
        g_resp = self.client.post("/api/groups/create", json={
            "name": "Batch Beta Retail",
            "description": "Retail partners"
        })
        self.assertEqual(g_resp.status_code, 200)
        group_id = g_resp.get_json()["group_id"]
        self.assertIsNotNone(group_id)

        # 2. Add client assigned to this group
        self.client.post("/api/clients/add", json={
            "name": "Retailer A",
            "email": "retailerA@example.com",
            "group_id": group_id,
            "is_active": 1
        })

        # Add an independent ungrouped client
        self.client.post("/api/clients/add", json={
            "name": "Ungrouped Client",
            "email": "solo@example.com",
            "is_active": 1
        })

        # Both should be active in get_active_clients
        active = get_active_clients(self.test_db)
        self.assertEqual(len(active), initial_active + 2)

        # 3. Turn off group (toggle active to 0)
        toggle_resp = self.client.post("/api/groups/toggle", json={"group_id": group_id})
        self.assertEqual(toggle_resp.status_code, 200)
        self.assertFalse(toggle_resp.get_json()["is_active"])

        # Now only the ungrouped client and previous clients should be due for reminders!
        active_after_pause = get_active_clients(self.test_db)
        self.assertEqual(len(active_after_pause), initial_active + 1)
        self.assertTrue(any(c["email"] == "solo@example.com" for c in active_after_pause))
        self.assertFalse(any(c["email"] == "retailerA@example.com" for c in active_after_pause))

        # 4. Turn group back on
        self.client.post("/api/groups/toggle", json={"group_id": group_id})
        self.assertEqual(len(get_active_clients(self.test_db)), initial_active + 2)

        # 5. Delete group
        del_g = self.client.post("/api/groups/delete", json={"group_id": group_id, "delete_clients": False})
        self.assertEqual(del_g.status_code, 200)
        groups = get_all_groups(self.test_db)
        self.assertEqual(len(groups), 0)

    def test_csv_upload_and_export(self):
        """Verify multipart CSV upload and CSV export."""
        self.client.post("/login", data={"username": "testadmin", "password": "testpass123"})

        csv_content = """name,email,company,project_name,reminder_note,daily_limit
Alice Smith,alice@example.com,Smith Co,PPC Ads,Review bids,100
Bob Jones,bob@example.com,Jones LLC,SEO Growth,Approve copy,50
Invalid Row,invalid-email-address,,,
"""
        data = {
            "file": (io.BytesIO(csv_content.encode("utf-8")), "clients_import.csv")
        }
        upload_resp = self.client.post("/api/clients/upload-csv", data=data, content_type="multipart/form-data")
        self.assertEqual(upload_resp.status_code, 200)
        res_json = upload_resp.get_json()
        self.assertTrue(res_json["success"])
        self.assertEqual(res_json["imported"], 2)
        self.assertEqual(res_json["skipped"], 1)

        # Test export
        export_resp = self.client.get("/api/clients/export-csv")
        self.assertEqual(export_resp.status_code, 200)
        self.assertIn("text/csv", export_resp.headers["Content-Type"])
        self.assertIn(b"alice@example.com", export_resp.data)
        self.assertIn(b"bob@example.com", export_resp.data)

    @patch.object(engine_manager, "start")
    @patch.object(engine_manager, "stop")
    def test_engine_toggle_api(self, mock_stop, mock_start):
        """Verify toggling 24/7 engine state via API."""
        self.client.post("/login", data={"username": "testadmin", "password": "testpass123"})

        # Toggle when not running -> calls start()
        engine_manager.is_running = False
        res = self.client.post("/api/engine/toggle")
        self.assertEqual(res.status_code, 200)
        mock_start.assert_called_once()

        # Toggle when running -> calls stop()
        engine_manager.is_running = True
        res2 = self.client.post("/api/engine/toggle")
        self.assertEqual(res2.status_code, 200)
        mock_stop.assert_called_once()
        engine_manager.is_running = False

    def test_templates_seeded_and_crud(self):
        """Verify initial templates are seeded and template CRUD APIs work."""
        self.client.post("/login", data={"username": "testadmin", "password": "testpass123"})

        # Initial seeding should have 3 starter templates
        t_resp = self.client.get("/api/templates")
        self.assertEqual(t_resp.status_code, 200)
        t_data = t_resp.get_json()
        self.assertTrue(t_data["success"])
        self.assertGreaterEqual(len(t_data["templates"]), 3)

        # Create new template
        create_resp = self.client.post("/api/templates/create", json={
            "name": "Custom Follow-Up Variant Z",
            "subject": "Status on {project_name}",
            "html_content": "<p>Hello {client_name}</p>",
            "text_content": "Hello {client_name}",
            "is_active": 1
        })
        self.assertEqual(create_resp.status_code, 200)
        new_tid = create_resp.get_json()["template_id"]
        self.assertIsNotNone(new_tid)

        # Duplicate template
        dup_resp = self.client.post("/api/templates/duplicate", json={"template_id": new_tid})
        self.assertEqual(dup_resp.status_code, 200)
        dup_tid = dup_resp.get_json()["template_id"]
        self.assertIsNotNone(dup_tid)

        # Toggle active
        toggle_resp = self.client.post("/api/templates/toggle", json={"template_id": dup_tid})
        self.assertEqual(toggle_resp.status_code, 200)
        self.assertFalse(toggle_resp.get_json()["is_active"])

        # Delete duplicate template
        del_resp = self.client.post("/api/templates/delete", json={"template_id": dup_tid})
        self.assertEqual(del_resp.status_code, 200)
        self.assertTrue(del_resp.get_json()["success"])

    def test_client_template_assignment_and_cyclic_rotation(self):
        """
        Verify assigning specific templates to a client and testing the auto-rotation engine:
        assert sequential sends cycle through assigned templates and never repeat back-to-back!
        """
        from mailer.database import (
            create_email_template,
            get_next_template_for_client,
            record_delivery,
            set_client_assigned_templates,
        )

        self.client.post("/login", data={"username": "testadmin", "password": "testpass123"})

        # Create 3 isolated templates
        t1 = create_email_template("Rot Alpha", "Alpha {project_name}", "<p>A</p>", "A", 1, self.test_db)
        t2 = create_email_template("Rot Beta", "Beta {project_name}", "<p>B</p>", "B", 1, self.test_db)
        t3 = create_email_template("Rot Gamma", "Gamma {project_name}", "<p>C</p>", "C", 1, self.test_db)

        cid = "client_rotation_test@example.com"
        self.client.post("/api/clients/add", json={
            "name": "Rotation Tester",
            "email": cid,
            "template_ids": [t1, t2, t3],
            "rotation_interval_minutes": 0 # rotate on every send
        })

        # 1. First send: should pick first eligible template (t1)
        next_t = get_next_template_for_client(cid, self.test_db)
        self.assertEqual(next_t["id"], t1)
        # Record send
        record_delivery(cid, cid, "Subj 1", 1, "SUCCESS", None, self.test_db, template_id=t1, template_name="Rot Alpha")

        # 2. Second send: should rotate to t2
        next_t2 = get_next_template_for_client(cid, self.test_db)
        self.assertEqual(next_t2["id"], t2)
        record_delivery(cid, cid, "Subj 2", 2, "SUCCESS", None, self.test_db, template_id=t2, template_name="Rot Beta")

        # 3. Third send: should rotate to t3
        next_t3 = get_next_template_for_client(cid, self.test_db)
        self.assertEqual(next_t3["id"], t3)
        record_delivery(cid, cid, "Subj 3", 3, "SUCCESS", None, self.test_db, template_id=t3, template_name="Rot Gamma")

        # 4. Fourth send: cycles back to t1 (never repeats consecutively)
        next_t4 = get_next_template_for_client(cid, self.test_db)
        self.assertEqual(next_t4["id"], t1)

    def test_template_time_based_rotation(self):
        """
        Verify time-based rotation: when rotation_interval_minutes is set (e.g. 60m),
        sends within the time window keep the template, then rotate once window elapses.
        """
        import time
        from mailer.database import (
            create_email_template,
            get_next_template_for_client,
            record_delivery,
        )

        self.client.post("/login", data={"username": "testadmin", "password": "testpass123"})

        t1 = create_email_template("Window A", "Sub A", "<p>A</p>", "A", 1, self.test_db)
        t2 = create_email_template("Window B", "Sub B", "<p>B</p>", "B", 1, self.test_db)

        cid = "time_client@example.com"
        self.client.post("/api/clients/add", json={
            "name": "Time Tester",
            "email": cid,
            "template_ids": [t1, t2],
            "rotation_interval_minutes": 60 # 60 minutes
        })

        # Record a send that just occurred (1 minute ago)
        now = time.time()
        record_delivery(cid, cid, "Subj A", 1, "SUCCESS", None, self.test_db, template_id=t1, template_name="Window A")

        # Within 60 min window: should still use t1
        curr = get_next_template_for_client(cid, self.test_db)
        self.assertEqual(curr["id"], t1)

        # Now simulate that 70 minutes have passed by backdating delivery_log sent_at
        conn = sqlite3 = __import__("sqlite3").connect(str(self.test_db))
        conn.execute("UPDATE delivery_logs SET sent_at = ? WHERE client_id = ?", (now - 4200, cid))
        conn.commit()
        conn.close()

        # Window elapsed: should rotate to t2!
        rotated = get_next_template_for_client(cid, self.test_db)
        self.assertEqual(rotated["id"], t2)


if __name__ == "__main__":
    unittest.main()
