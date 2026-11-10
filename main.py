#!/usr/bin/env python3
"""
Marketing SMTP Work Reminder System - CLI Entry Point.
Manages 24/7 scheduled client work reminders with rolling 24h limits.
"""

import argparse
from datetime import datetime
import os
import sys
import time

from mailer.clients import sync_clients
from mailer.config import Config
from mailer.database import get_client_summary_stats, init_db
from mailer.engine import DispatchEngine
from mailer.smtp_client import SMTPClient
from mailer.templates import create_reminder_message


def cmd_sync(args):
    """Synchronize clients from data/clients.csv or data/clients.json into database."""
    init_db(Config.DATABASE_PATH)
    count = sync_clients(Config.DATABASE_PATH, Config.CLIENTS_CSV_PATH, Config.CLIENTS_JSON_PATH)
    print(f"\n[+] Successfully synchronized {count} client(s) into database: {Config.DATABASE_PATH}")
    print(f"    Source file: {Config.CLIENTS_CSV_PATH if Config.CLIENTS_CSV_PATH.is_file() else Config.CLIENTS_JSON_PATH}\n")


def cmd_status(args):
    """Display real-time delivery status, 24h quotas, and metrics for all clients."""
    init_db(Config.DATABASE_PATH)
    # Ensure database has latest clients
    sync_clients(Config.DATABASE_PATH, Config.CLIENTS_CSV_PATH, Config.CLIENTS_JSON_PATH)
    
    stats = get_client_summary_stats(Config.DATABASE_PATH, Config.WINDOW_HOURS)
    
    print("\n" + "=" * 90)
    print("                  CLIENT WORK REMINDER SYSTEM - 24-HOUR STATUS")
    print("=" * 90)
    print(f"{'Client Name':<20} {'Email':<26} {'Company':<16} {'Sent (24h)':<12} {'Remaining':<10} {'Last Sent':<14}")
    print("-" * 90)
    
    total_sent = 0
    total_remaining = 0
    
    for s in stats:
        name = (s["name"][:18] + "..") if len(s["name"]) > 18 else s["name"]
        email = (s["email"][:24] + "..") if len(s["email"]) > 24 else s["email"]
        company = (s["company"][:14] + "..") if len(s["company"]) > 14 else s["company"]
        sent_str = f"{s['sent_24h']}/{s['daily_limit']}"
        rem_str = str(s["remaining_quota"])
        
        if s["last_sent"]:
            last_dt = datetime.fromtimestamp(s["last_sent"])
            last_str = last_dt.strftime("%H:%M:%S")
        else:
            last_str = "Never"
            
        total_sent += s["sent_24h"]
        total_remaining += s["remaining_quota"]
        
        print(f"{name:<20} {email:<26} {company:<16} {sent_str:<12} {rem_str:<10} {last_str:<14}")
        
    print("-" * 90)
    print(f"Total Active Clients: {len(stats)} | Total Delivered (Last 24h): {total_sent} | Quota Remaining: {total_remaining}")
    print("=" * 90 + "\n")


def cmd_test(args):
    """Test Webmail SMTP connection and optionally send a sample reminder email."""
    init_db(Config.DATABASE_PATH)
    
    print("\n" + "=" * 65)
    print("               WEBMAIL SMTP DIAGNOSTIC TEST")
    print("=" * 65)
    print(f" Host     : {Config.SMTP_HOST}:{Config.SMTP_PORT}")
    print(f" Username : {Config.SMTP_USER}")
    print(f" Mode     : SSL={Config.SMTP_USE_SSL}, TLS={Config.SMTP_USE_TLS}")
    print("-" * 65)
    
    client = SMTPClient(
        host=Config.SMTP_HOST,
        port=Config.SMTP_PORT,
        username=Config.SMTP_USER,
        password=Config.SMTP_PASSWORD,
        use_ssl=Config.SMTP_USE_SSL,
        use_tls=Config.SMTP_USE_TLS,
    )
    
    print("Testing connection to Webmail SMTP server... ", end="", flush=True)
    ok, message = client.test_connection()
    if ok:
        print("SUCCESS!")
        print(f"Status: {message}\n")
    else:
        print("FAILED!")
        print(f"Error : {message}\n")
        print("Check your .env settings: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD.")
        return

    recipient = args.recipient
    if not recipient:
        recipient = input("Enter an email address to send a sample test reminder (or press Enter to skip): ").strip()
        
    if recipient:
        print(f"Dispatching test reminder to {recipient}...")
        test_client = {
            "name": "Valued Test Client",
            "email": recipient,
            "company": "Sample Marketing Client",
            "project_name": "Full-Service Marketing & Branding",
            "reminder_note": "This is a diagnostic sample work update confirming template styling and Webmail delivery.",
            "daily_limit": 100,
        }
        msg = create_reminder_message(
            client=test_client,
            sequence_num=1,
            sender_name=Config.SENDER_NAME,
            sender_email=Config.SENDER_EMAIL,
            subject_prefix=Config.EMAIL_SUBJECT,
            html_template_path=Config.HTML_TEMPLATE_PATH,
            text_template_path=Config.TEXT_TEMPLATE_PATH,
        )
        sent, err = client.send_email(Config.SENDER_EMAIL, recipient, msg)
        if sent:
            print(f"[+] Test email successfully delivered to {recipient}!")
        else:
            print(f"[-] Test email failed: {err}")


def cmd_start(args):
    """Launch the 24/7 background dispatcher daemon."""
    init_db(Config.DATABASE_PATH)
    sync_clients(Config.DATABASE_PATH, Config.CLIENTS_CSV_PATH, Config.CLIENTS_JSON_PATH)
    engine = DispatchEngine(Config)
    engine.run_forever()


def main():
    parser = argparse.ArgumentParser(
        description="Marketing SMTP Work Reminder System - 24/7 Client Notification Suite",
        epilog="Automates scheduled client work reminders while enforcing strict 24h rolling quotas (100 emails/day)."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: gui
    parser_gui = subparsers.add_parser("gui", help="Launch the Desktop GUI Application")

    # Command: start
    parser_start = subparsers.add_parser("start", help="Start the 24/7 continuous work reminder dispatcher (headless CLI)")
    
    # Command: status
    parser_status = subparsers.add_parser("status", help="Show 24-hour delivery status and remaining client quotas")

    # Command: sync
    parser_sync = subparsers.add_parser("sync", help="Synchronize clients.csv / clients.json into SQLite database")

    # Command: test
    parser_test = subparsers.add_parser("test", help="Test Webmail SMTP connection and send a sample reminder email")
    parser_test.add_argument("-r", "--recipient", help="Recipient email address for the test reminder")

    # Command: cli
    parser_cli = subparsers.add_parser("cli", help="Display interactive terminal menu")

    args = parser.parse_args()

    if args.command == "start":
        cmd_start(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "sync":
        cmd_sync(args)
    elif args.command == "test":
        cmd_test(args)
    elif args.command == "cli":
        print("\n=======================================================")
        print("      Marketing SMTP Work Reminder System (v2.0)")
        print("=======================================================")
        print("  1. python main.py gui     - Launch Modern Desktop Application")
        print("  2. python main.py start   - Run the 24/7 continuous dispatcher")
        print("  3. python main.py status  - View delivery counts and quotas")
        print("  4. python main.py test    - Test Webmail SMTP connection & send test")
        print("  5. python main.py sync    - Reload data/clients.csv into database")
        print("=======================================================\n")
        cmd_status(args)
    else:
        # Default behavior: Launch modern desktop app
        try:
            from gui.app import launch_gui
            launch_gui()
        except Exception as e:
            print(f"[!] Could not launch desktop GUI: {e}")
            print("    Falling back to terminal status:")
            cmd_status(args)


if __name__ == "__main__":
    main()
