"""
24/7 Scheduling and Dispatch Engine.
Enforces per-client 24-hour rate limits (default: 100 emails/24h),
paces deliveries evenly across the day, and handles continuous round-robin execution.
"""

from datetime import datetime
import signal
import sys
import threading
import time
from typing import Any, Dict, List, Optional

from mailer.config import Config
from mailer.database import (
    get_active_clients,
    get_client_last_sent_time,
    get_client_sends_in_window,
    get_next_template_for_client,
    record_delivery,
)
from mailer.smtp_client import SMTPClient
from mailer.templates import create_reminder_message


class DispatchEngine:
    """
    Continuous 24/7 background scheduler for client work reminders.
    """

    def __init__(self, config: Config = Config):
        self.config = config
        self.smtp_client = SMTPClient(
            host=config.SMTP_HOST,
            port=config.SMTP_PORT,
            username=config.SMTP_USER,
            password=config.SMTP_PASSWORD,
            use_ssl=config.SMTP_USE_SSL,
            use_tls=config.SMTP_USE_TLS,
        )
        self.stop_event = threading.Event()
        self._consecutive_failures: Dict[str, int] = {}

    def is_client_due(self, client: Dict[str, Any], now: float) -> bool:
        """
        Check if a client is eligible for their next scheduled work reminder.
        Criteria:
        1. Client must have sent < daily_limit emails within the rolling 24-hour window.
        2. Elapsed time since client's last send >= min_interval (or cooldown after failure).
        """
        cid = client["client_id"]
        limit = client.get("daily_limit", self.config.DAILY_CAP_PER_CLIENT)

        # Check rolling window count
        sent_in_window = get_client_sends_in_window(
            client_id=cid,
            window_hours=self.config.WINDOW_HOURS,
            db_path=self.config.DATABASE_PATH,
        )
        if sent_in_window >= limit:
            return False

        last_sent = get_client_last_sent_time(
            client_id=cid,
            db_path=self.config.DATABASE_PATH,
        )

        # If client has never received an email yet, they are immediately due
        if last_sent is None:
            return True

        # Check pacing interval
        elapsed = now - last_sent
        # If client recently failed, apply a 60-second cooldown
        recent_fails = self._consecutive_failures.get(cid, 0)
        cooldown = 60.0 if recent_fails > 0 else self.config.MIN_INTERVAL_SECONDS

        return elapsed >= cooldown

    def dispatch_for_client(self, client: Dict[str, Any]) -> bool:
        """
        Prepare and dispatch a work reminder email for a single client.
        """
        cid = client["client_id"]
        recipient = client["email"]
        client_name = client.get("name", recipient)
        company = client.get("company", "Client")

        # Determine next sequence number (1 to 100)
        sent_in_window = get_client_sends_in_window(
            client_id=cid,
            window_hours=self.config.WINDOW_HOURS,
            db_path=self.config.DATABASE_PATH,
        )
        sequence_num = sent_in_window + 1
        limit = client.get("daily_limit", self.config.DAILY_CAP_PER_CLIENT)

        # Select next rotating template for client
        template = get_next_template_for_client(cid, self.config.DATABASE_PATH)
        template_name = template["name"] if template else "Default Template"
        template_id = template["id"] if template else None

        msg = create_reminder_message(
            client=client,
            sequence_num=sequence_num,
            sender_name=self.config.SENDER_NAME,
            sender_email=self.config.SENDER_EMAIL,
            subject_prefix=self.config.EMAIL_SUBJECT,
            html_template_path=self.config.HTML_TEMPLATE_PATH,
            text_template_path=self.config.TEXT_TEMPLATE_PATH,
            template_data=template,
        )

        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{time_str}] -> Dispatching to {client_name} ({recipient}) [#{sequence_num}/{limit}] [{template_name}]... ", end="", flush=True)

        success, error = self.smtp_client.send_email(
            sender=self.config.SENDER_EMAIL,
            recipient=recipient,
            message=msg,
        )

        if success:
            record_delivery(
                client_id=cid,
                recipient_email=recipient,
                subject=msg["Subject"],
                sequence_num=sequence_num,
                status="SUCCESS",
                error_message=None,
                db_path=self.config.DATABASE_PATH,
                template_id=template_id,
                template_name=template_name,
            )
            self._consecutive_failures[cid] = 0
            remaining = max(0, limit - sequence_num)
            print(f"DELIVERED [{template_name}] (Remaining 24h Quota: {remaining})")
            return True
        else:
            record_delivery(
                client_id=cid,
                recipient_email=recipient,
                subject=msg["Subject"],
                sequence_num=sequence_num,
                status="FAILED",
                error_message=error,
                db_path=self.config.DATABASE_PATH,
                template_id=template_id,
                template_name=template_name,
            )
            self._consecutive_failures[cid] = self._consecutive_failures.get(cid, 0) + 1
            print(f"FAILED: {error}")
            return False

    def run_forever(self):
        """
        Continuous 24/7 service loop.
        Monitors client list, evaluates 24-hour rate limits, and triggers deliveries.
        """
        print("=" * 70)
        print("     MARKETING SMTP WORK REMINDER SYSTEM - 24/7 DISPATCHER")
        print("=" * 70)
        print(f" Webmail Host   : {self.config.SMTP_HOST}:{self.config.SMTP_PORT} (SSL: {self.config.SMTP_USE_SSL}, TLS: {self.config.SMTP_USE_TLS})")
        print(f" Sender Profile : {self.config.SENDER_NAME} <{self.config.SENDER_EMAIL}>")
        print(f" Daily Quota    : {self.config.DAILY_CAP_PER_CLIENT} emails per client per {self.config.WINDOW_HOURS} hours")
        print(f" Client Pacing  : ~{self.config.MIN_INTERVAL_SECONDS / 60:.1f} minutes between emails per client")
        print(f" Inter-delay    : {self.config.GLOBAL_DISPATCH_DELAY}s between outbound transmissions")
        print("=" * 70)
        print(" [i] Press Ctrl+C at any time to gracefully halt the service.\n")

        # Initial Webmail connection check
        print("Verifying Webmail SMTP connection... ", end="", flush=True)
        ok, msg = self.smtp_client.test_connection()
        if not ok:
            print(f"\n[!] WARNING: Could not connect to Webmail server:\n    {msg}")
            print("    The dispatcher will still run and retry connections on schedule.\n")
        else:
            print("OK [Connected]\n")

        while not self.stop_event.is_set():
            try:
                clients = get_active_clients(self.config.DATABASE_PATH)
                if not clients:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No active clients found in database. Sleeping 15s...")
                    self.stop_event.wait(15.0)
                    continue

                dispatched_in_cycle = 0
                now = time.time()

                for client in clients:
                    if self.stop_event.is_set():
                        break

                    if self.is_client_due(client, now):
                        self.dispatch_for_client(client)
                        dispatched_in_cycle += 1

                        # Global delay to prevent throttling by Webmail server
                        if self.config.GLOBAL_DISPATCH_DELAY > 0:
                            self.stop_event.wait(self.config.GLOBAL_DISPATCH_DELAY)

                # If no clients were due this cycle, sleep briefly before next check
                if dispatched_in_cycle == 0:
                    self.stop_event.wait(5.0)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[!] Dispatcher error: {e}")
                self.stop_event.wait(10.0)

        print("\n[i] 24/7 Dispatcher safely terminated.")

