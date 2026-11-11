"""
Automated unit and integration tests for Marketing Mailer Web Version.
"""

import os
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import unittest

from mailer.config import Config
from mailer.database import get_all_clients, init_db
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


if __name__ == "__main__":
    unittest.main()

