"""
Web Engine Service Controller.
Manages the background 24/7 DispatchEngine daemon thread, live activity buffer, and status.
"""

from collections import deque
from datetime import datetime
import threading
import time
from typing import Any, Dict, List

from mailer.config import Config
from mailer.database import (
    get_active_clients,
    get_client_sends_in_window,
    get_next_template_for_client,
    record_delivery,
)
from mailer.engine import DispatchEngine
from mailer.templates import create_reminder_message


class WebEngineManager:
    """Singleton manager coordinating the 24/7 background reminder dispatcher in the web app."""

    def __init__(self):
        self.engine = DispatchEngine(Config)
        self.is_running = False
        self._thread = None
        self._lock = threading.Lock()
        self.logs_buffer = deque(maxlen=200)
        self.add_log("INFO", "Web Mailer service initialized and ready.")

    def add_log(self, level: str, message: str):
        with self._lock:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.logs_buffer.append({
                "time": timestamp,
                "level": level,
                "message": message,
            })

    def get_logs(self, limit: int = 50) -> List[Dict[str, str]]:
        with self._lock:
            return list(self.logs_buffer)[-limit:]

    def start(self):
        with self._lock:
            if self.is_running:
                return

            self.is_running = True
            self.engine.stop_event.clear()
            self.add_log("INFO", "Starting 24/7 background reminder engine...")

            def _worker_loop():
                ok, msg = self.engine.smtp_client.test_connection()
                if ok:
                    self.add_log("SUCCESS", f"Connected to Webmail SMTP: {Config.SMTP_HOST}:{Config.SMTP_PORT}")
                else:
                    self.add_log("WARN", f"Webmail connection warning: {msg}")

                while not self.engine.stop_event.is_set():
                    try:
                        clients = get_active_clients(Config.DATABASE_PATH)
                        if not clients:
                            self.add_log("INFO", "No active clients in roster. Sleeping 15s...")
                            self.engine.stop_event.wait(15.0)
                            continue

                        dispatched_count = 0
                        now = time.time()

                        for client in clients:
                            if self.engine.stop_event.is_set():
                                break

                            if self.engine.is_client_due(client, now):
                                cid = client["client_id"]
                                recipient = client["email"]
                                name = client.get("name", recipient)
                                limit = client.get("daily_limit", Config.DAILY_CAP_PER_CLIENT)

                                sent_in_window = get_client_sends_in_window(
                                    cid, Config.WINDOW_HOURS, Config.DATABASE_PATH
                                )
                                seq = sent_in_window + 1

                                # Select next rotating template for client
                                template = get_next_template_for_client(cid, Config.DATABASE_PATH)
                                template_name = template["name"] if template else "Default Template"
                                template_id = template["id"] if template else None

                                self.add_log("INFO", f"Sending reminder #{seq}/{limit} [{template_name}] to {name} ({recipient})...")

                                msg = create_reminder_message(
                                    client=client,
                                    sequence_num=seq,
                                    sender_name=Config.SENDER_NAME,
                                    sender_email=Config.SENDER_EMAIL,
                                    subject_prefix=Config.EMAIL_SUBJECT,
                                    html_template_path=Config.HTML_TEMPLATE_PATH,
                                    text_template_path=Config.TEXT_TEMPLATE_PATH,
                                    template_data=template,
                                )

                                success, err = self.engine.smtp_client.send_email(
                                    sender=Config.SENDER_EMAIL,
                                    recipient=recipient,
                                    message=msg,
                                )

                                if success:
                                    record_delivery(
                                        client_id=cid,
                                        recipient_email=recipient,
                                        subject=msg["Subject"],
                                        sequence_num=seq,
                                        status="SUCCESS",
                                        error_message=None,
                                        db_path=Config.DATABASE_PATH,
                                        template_id=template_id,
                                        template_name=template_name,
                                    )
                                    rem = max(0, limit - seq)
                                    self.add_log("SUCCESS", f"Delivered [{template_name}] to {name}! (Remaining 24h Quota: {rem})")
                                else:
                                    record_delivery(
                                        client_id=cid,
                                        recipient_email=recipient,
                                        subject=msg["Subject"],
                                        sequence_num=seq,
                                        status="FAILED",
                                        error_message=err,
                                        db_path=Config.DATABASE_PATH,
                                        template_id=template_id,
                                        template_name=template_name,
                                    )
                                    self.add_log("ERROR", f"Delivery failed for {name}: {err}")

                                dispatched_count += 1
                                if Config.GLOBAL_DISPATCH_DELAY > 0:
                                    self.engine.stop_event.wait(Config.GLOBAL_DISPATCH_DELAY)

                        if dispatched_count == 0:
                            self.engine.stop_event.wait(5.0)

                    except Exception as e:
                        self.add_log("ERROR", f"Engine loop exception: {e}")
                        self.engine.stop_event.wait(10.0)

                self.add_log("INFO", "24/7 background reminder engine stopped.")

            self._thread = threading.Thread(target=_worker_loop, daemon=True)
            self._thread.start()

    def stop(self):
        with self._lock:
            if not self.is_running:
                return
            self.engine.stop_event.set()
            self.is_running = False
            self.add_log("INFO", "24/7 background reminder engine paused by user.")


# Global singleton manager instance
engine_manager = WebEngineManager()

