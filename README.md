# Marketing SMTP Work Reminder System

<p align="center">
  <strong>24/7 Automated Client Communication & Work Reminder Suite</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue.svg?style=flat-square" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/Dependencies-Zero%20External-brightgreen.svg?style=flat-square" alt="Zero Dependencies">
  <img src="https://img.shields.io/badge/Webmail-Ready-orange.svg?style=flat-square" alt="Webmail Ready">
  <img src="https://img.shields.io/badge/License-GPL%20v3-blue.svg?style=flat-square" alt="GPL v3">
</p>

---

## Overview

The **Marketing SMTP Work Reminder System** is an automated, continuous 24/7 background mailer built specifically for marketing agencies, client relations teams, and digital service providers.

It regularly transmits work updates and milestone reminders to your portfolio of clients (e.g. 30 clients), with strict **rolling 24-hour delivery limits** (default: 100 emails per client per 24 hours). 

### Key Capabilities

- **Strict 24-Hour Rolling Quotas:** Accurately tracks deliveries per client in a persistent SQLite database (`data/mailer.db`). Clients will never exceed 100 emails in any 24-hour window.
- **Smart Pacing & Anti-Spam Throttling:** Spreads the 100 emails smoothly across the 24-hour day (~1 email every 14.4 minutes per client) rather than blasting emails all at once, protecting your domain's sender reputation.
- **Webmail & Custom Domain Optimized:** Seamlessly connects to your agency's Webmail SMTP server (cPanel, DirectAdmin, Plesk, or custom domain relays) via Port 465 (SSL) or Port 587 (TLS).
- **User-Friendly Client Management:** Manage all clients in a simple, spreadsheet-friendly CSV file (`data/clients.csv`) or JSON (`data/clients.json`).
- **Agency-Branded Email Templates:** Ships with a responsive, modern HTML email template (`templates/reminder.html`) with milestone highlights, progress counters, and automatic fallback plain-text (`templates/reminder.txt`).
- **RFC 5322 Compliant:** Automatically generates unique `Message-ID`, timestamped `Date`, and bulk headers to pass spam filter checks.
- **Zero Mandatory External Dependencies:** Built entirely on Python 3 standard libraries (`sqlite3`, `smtplib`, `ssl`, `email`, `csv`, `json`, `threading`). Runs out of the box on any system.

---

## Quick Start Guide

### 1. Configure Webmail SMTP Credentials

Copy the template configuration file:

```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in your Webmail SMTP credentials:

```ini
# Webmail SMTP Server Details
SMTP_HOST=mail.youragency.com
SMTP_PORT=465
SMTP_USER=reminders@youragency.com
SMTP_PASSWORD=YourSecurePasswordHere

# Security Protocol
SMTP_USE_SSL=true
SMTP_USE_TLS=false

# Agency Profile
SENDER_NAME=Marketing Operations Team
SENDER_EMAIL=reminders@youragency.com
EMAIL_SUBJECT=Work Progress & Action Items Reminder

# Rate Limiting (100 emails per client in 24 hours)
DAILY_CAP_PER_CLIENT=100
WINDOW_HOURS=24.0
```

---

### 2. Add or Edit Your Clients

Open `data/clients.csv` in Excel, Google Sheets, or any text editor. Pre-filled with 30 sample client slots:

```csv
name,email,company,project_name,reminder_note,daily_limit,is_active
John Doe,client1@example.com,Apex Retail,SEO & Content Growth,Review draft articles and approve Q3 keyword list,100,1
Sarah Jenkins,client2@example.com,Nexus Tech,Google Ads PPC,Bid strategy adjustments and search term audit in progress,100,1
Michael Chang,client3@example.com,Lumen City,Brand Identity & Creative,Final logo and typography guidelines ready for feedback,100,1
```

- `name`: Client contact name.
- `email`: Client recipient address.
- `company`: Client company or organization.
- `project_name`: Deliverable or marketing campaign title.
- `reminder_note`: Current milestone or work item to display in the email card.
- `daily_limit`: Maximum emails for this client per 24 hours (default: `100`).
- `is_active`: `1` to send reminders, `0` to pause this client.

---

### 3. Test Your Webmail Connection

Before running the 24/7 service, verify your Webmail connection and send a test reminder:

```bash
python main.py test
```

Or send directly to your personal email to preview the styling:

```bash
python main.py test --recipient your_email@domain.com
```

---

### 4. Check Current Status & Quotas

View your client list, emails delivered in the last 24 hours, remaining quotas, and last delivery timestamps:

```bash
python main.py status
```

Output:
```text
==========================================================================================
                  CLIENT WORK REMINDER SYSTEM - 24-HOUR STATUS
==========================================================================================
Client Name          Email                      Company          Sent (24h)   Remaining  Last Sent     
------------------------------------------------------------------------------------------
John Doe             client1@example.com        Apex Retail      0/100        100        Never         
Sarah Jenkins        client2@example.com        Nexus Tech       0/100        100        Never         
Michael Chang        client3@example.com        Lumen City       0/100        100        Never         
...
------------------------------------------------------------------------------------------
Total Active Clients: 30 | Total Delivered (Last 24h): 0 | Quota Remaining: 3000
==========================================================================================
```

---

### 5. Launch the 24/7 Continuous Dispatcher

Start the background service:

```bash
python main.py start
```

The system will:
1. Automatically load and sync `data/clients.csv` into the SQLite database.
2. Verify the Webmail SMTP connection.
3. Continuously cycle through active clients in round-robin fashion.
4. Calculate pacing intervals (~14.4 minutes between emails per client) and dispatch reminder emails.
5. Record every delivery with exact timestamps in SQLite.
6. When a client reaches their 100-email cap, pause further sends for that client until older deliveries roll out of the 24-hour window.

To stop the dispatcher safely at any time, press `Ctrl+C`.

---

## Running Continuously in Production (24/7)

### On Windows
You can run it in a PowerShell or CMD window, or schedule it via Windows Task Scheduler. To keep it running persistently in the background:
```powershell
Start-Process python -ArgumentList "main.py start" -WindowStyle Hidden
```

### On Linux / VPS / Cloud Server
You can run it inside `tmux`, `screen`, or as a `systemd` service:

```ini
# /etc/systemd/system/marketing-mailer.service
[Unit]
Description=Marketing SMTP Work Reminder 24/7 Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/EmailBomber
ExecStart=/usr/bin/python3 main.py start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Customizing the Email Template

The email template lives in `templates/reminder.html` and `templates/reminder.txt`. You can edit the colors, agency logo, or layout using standard HTML.

The following dynamic tags are automatically populated for every email:

| Placeholder | Description |
| :--- | :--- |
| `{client_name}` | Name of the client contact |
| `{client_email}` | Recipient email address |
| `{company}` | Client company name |
| `{project_name}` | Marketing project or campaign title |
| `{reminder_note}` | Current work item or milestone text |
| `{sequence_num}` | Current delivery number in the 24h cycle (e.g., 1 to 100) |
| `{daily_limit}` | Client's 24-hour limit (e.g., 100) |
| `{current_date}` | Formatted date (e.g. `Nov 10, 2026`) |
| `{current_time}` | Formatted time (e.g. `15:30:00`) |
| `{sender_name}` | Agency sender name configured in `.env` |
| `{sender_email}` | Agency sender email configured in `.env` |

---

## CLI Command Reference

| Command | Description |
| :--- | :--- |
| `python main.py start` | Start the 24/7 background reminder dispatcher |
| `python main.py status` | Display 24-hour delivery status and remaining client quotas |
| `python main.py sync` | Manually reload `data/clients.csv` into the database |
| `python main.py test` | Test Webmail connection and send a sample email |
| `python main.py test -r <email>` | Send a test reminder to a specific email address |

---

## Running Automated Tests

A unit test suite is included to verify rolling 24-hour limits, database persistence, pacing, and template formatting:

```bash
python -m unittest discover -s tests
```

---

## License

This software is released under the **GNU General Public License v3.0 (GPL-3.0)**.
Copyright &copy; 2026 Sagar Biswas. All rights reserved.
