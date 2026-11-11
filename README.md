# Marketing Mailer Desktop

<p align="center">
  <strong>Modern Windows Desktop Application for 24/7 Client Work Reminders & Marketing SMTP Automation</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-blue?style=flat-square&logo=windows" alt="Platform: Windows 10 | 11">
  <img src="https://img.shields.io/badge/UI-Modern%20Dark%20%2F%20Light-8b5cf6?style=flat-square" alt="Dark / Light Theme">
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue.svg?style=flat-square&logo=python" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/Webmail-cPanel%20%7C%20Plesk%20%7C%20DirectAdmin-orange?style=flat-square" alt="Webmail Ready">
  <img src="https://img.shields.io/badge/System%20Tray-24%2F7%20Background-emerald?style=flat-square" alt="System Tray">
  <img src="https://img.shields.io/badge/Packaging-One--Click%20EXE-brightgreen?style=flat-square" alt="One-Click EXE">
  <img src="https://img.shields.io/badge/License-GPL%20v3-blue.svg?style=flat-square" alt="License: GPL v3">
</p>

---

## Overview

**Marketing Mailer Desktop** is a lightweight, human-crafted Windows desktop application designed for marketing firms, digital agencies, and account management teams.

It automates the scheduled delivery of daily project work updates and milestone reminders to your client roster (e.g. 30 clients), running **24/7 continuously in the background** while enforcing strict **rolling 24-hour rate limits** (default: 100 emails per client per 24 hours).

Built with non-technical office staff in mind, the application requires **no command line or technical knowledge**—everything can be monitored, configured, and controlled through an intuitive modern interface.

```
+====================================================================================================+
|  [⚡ Marketing Mailer v2.0]     [📊 Dashboard]   [👥 Clients (30)]   [✉️ Email Template]   [⚙️ Settings] |
+====================================================================================================+
|                                                                                                    |
|  +-- [🟢 24/7 SERVICE ACTIVE] --------------------------------------------- [⏸  Pause Service] --+  |
|  |  Pacing: ~14.4 mins between emails per client | Enforcing 100 emails/24h per client quota.     |  |
|  +------------------------------------------------------------------------------------------------+  |
|                                                                                                    |
|  +------------------+  +------------------+  +------------------+  +----------------------------+  |
|  |  ACTIVE CLIENTS  |  |  DELIVERED (24H) |  |  QUOTA REMAINING |  |        WEBMAIL RELAY       |  |
|  |        30        |  |       142        |  |      2,858       |  |   mail.youragency.com:465  |  |
|  +------------------+  +------------------+  +------------------+  +----------------------------+  |
|                                                                                                    |
|  +-- LIVE TRANSMISSION FEED --------------------------------------------------- [Clear Feed] ----+  |
|  | [15:30:12] -> Dispatching to Apex Retail (client1@example.com) [#12/100]... DELIVERED         |  |
|  | [15:32:15] -> Dispatching to Nexus Tech (client2@example.com) [#12/100]... DELIVERED          |  |
|  | [15:34:20] -> Dispatching to Lumen City (client3@example.com) [#12/100]... DELIVERED          |  |
|  +------------------------------------------------------------------------------------------------+  |
+====================================================================================================+
```

---

## Key Features

### 🖥️ Human-Crafted Windows Desktop Interface
- **Office Dark & Light Modes:** Elegant dark aesthetic by default, with an instant toggle for light theme or Windows system matching in the Settings tab.
- **Native Typography & High DPI:** Built with Segoe UI fonts, rounded metric cards, clear color-coded status badges, and responsive tables.
- **Single-Click Controls:** Start or pause the entire 24/7 delivery loop with a single master button on the dashboard.

### ⏱️ Strict 24-Hour Rolling Quotas & Anti-Spam Pacing
- **Persistent SQLite Tracking:** Delivery logs are stored in `data/mailer.db`. Delivery counts survive application restarts and power outages.
- **Rolling 24h Enforcement:** Each client has a configurable cap (default: `100` emails in 24 hours). If a client reaches 100, the system automatically pauses that client until older emails roll out of the 24-hour window.
- **Smart Pacing:** Smoothly paces out the 100 emails (~1 email every 14.4 minutes per client) rather than blasting 100 emails at once, protecting your sender domain reputation.
- **Global Dispatch Delay:** Introduces a safety pause (default: 2.0s) between outbound messages across different clients to avoid triggering server rate limits.

### 👥 Client Roster Management
- **Interactive Spreadsheet Table:** View all 30 clients with live status, company name, project scope, milestone notes, and 24h quota counters.
- **Real-Time Search:** Search clients instantly by name, email, or company.
- **Add / Edit Modal Dialogs:** Friendly popup forms to update client contact details, project milestones, or daily limits without touching code.
- **Excel & CSV Friendly:** Manage clients in `data/clients.csv` and sync into the app with a single click.

### ✉️ Live Template Preview & Test Sends
- **Interactive Client Preview:** Pick any client from the dropdown to preview how their email will look with their real project details.
- **Readable & HTML Source Modes:** Easily inspect formatted text or raw HTML email source.
- **One-Click Personal Test Send:** Send an immediate preview to your own personal email to review rendering in Outlook, Gmail, or Webmail.

### ⚙️ Dedicated Webmail Settings Panel
- **Designed for Webmail Relays:** Tailored for custom domain SMTP servers (cPanel, DirectAdmin, Plesk, and private SMTP relays).
- **One-Click Connection Diagnostic:** A dedicated **"Test Webmail Connection"** button verifies credentials and returns instant green/red status before starting dispatches.
- **Masked Password Field:** Toggle password visibility safely in open office environments.

### 🔔 System Tray & 24/7 Background Running
- **Smart Window Close Interceptor:** Clicking `[X]` asks whether to minimize to the Windows system tray or exit completely.
- **Silent Background Operation:** When minimized, the application runs silently in the Windows taskbar notification area with a custom mail tray icon. Double-clicking the tray icon restores the window instantly.

### 📦 One-Click Standalone Executable (`.exe`)
- Includes `scripts/build_windows_exe.bat`, an automated script that compiles the entire project into a portable standalone `MarketingMailer.exe` requiring **no Python installation on staff PCs**.

---

## Quick Start & Running the App

### Option A: Running from Source

#### 1. Clone the Repository
```bash
git clone https://github.com/SagarBiswas-MultiHAT/MarketingMailer.git
cd MarketingMailer
```

#### 2. Install Requirements
```bash
pip install -r requirements.txt
```

#### 3. Launch the Desktop Application
Double-click `desktop_launcher.pyw` (runs without opening a command window), or run via terminal:
```bash
python main.py
```

---

### Option B: Compiling the Standalone Executable (`.exe`)

To generate a standalone `MarketingMailer.exe` that can be copied to any office PC without installing Python:

1. Double-click the one-click build script:
   ```bat
   scripts\build_windows_exe.bat
   ```
2. Once complete, your portable application will be located inside:
   ```
   dist\MarketingMailer\MarketingMailer.exe
   ```
3. Copy the `dist\MarketingMailer` folder to any office Windows workstation and run!

---

### Option C: Hosting the Web Version on a Contabo VPS (with Custom Domain)

You can run the web dashboard on your Contabo server alongside your existing applications without port conflicts:

#### 1. Clone & Install on Contabo VPS
```bash
git clone https://github.com/SagarBiswas-MultiHAT/MarketingMailer.git /var/www/MarketingMailer
cd /var/www/MarketingMailer
pip install -r requirements.txt
```

#### 2. Configure `.env`
Set your Webmail credentials and web admin password:
```ini
SMTP_HOST=mail.youragency.com
SMTP_PORT=465
SMTP_USER=reminders@youragency.com
SMTP_PASSWORD=YourPassword

WEB_ADMIN_USER=admin
WEB_ADMIN_PASSWORD=YourSecurePassword
PORT=8085
```

#### 3. Enable 24/7 Systemd Background Service
```bash
sudo cp deployment/marketing-mailer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable marketing-mailer
sudo systemctl start marketing-mailer
```

#### 4. Connect Your Domain with Nginx & Let's Encrypt SSL
1. Set up your domain's DNS A record pointing to your Contabo server IP (e.g. `reminders.yourdomain.com`).
2. Copy the Nginx configuration:
   ```bash
   sudo cp deployment/nginx-marketing-mailer.conf /etc/nginx/sites-available/marketing-mailer.conf
   ```
3. Update `server_name reminders.yourdomain.com;` inside `/etc/nginx/sites-available/marketing-mailer.conf`.
4. Link and reload Nginx:
   ```bash
   sudo ln -s /etc/nginx/sites-available/marketing-mailer.conf /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```
5. Install free SSL with Certbot:
   ```bash
   sudo certbot --nginx -d reminders.yourdomain.com
   ```
6. Access your secure dashboard at `https://reminders.yourdomain.com` from anywhere!

---

## Configuration Guide

### 1. Webmail SMTP Settings
You can configure your Webmail SMTP credentials directly inside the **⚙️ Settings** tab in the desktop application, or by creating a `.env` file from the example:

```bash
cp .env.example .env
```

Define your settings:
```ini
# Webmail SMTP Server Details (cPanel / Custom Domain)
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

# Rate Limiting & Quotas
DAILY_CAP_PER_CLIENT=100
WINDOW_HOURS=24.0
GLOBAL_DISPATCH_DELAY=2.0
```

---

### 2. Client Roster (`data/clients.csv`)

The application comes pre-loaded with **30 client slots** in `data/clients.csv` that can be edited in Excel or directly in the app's **👥 Clients** tab:

```csv
name,email,company,project_name,reminder_note,daily_limit,is_active
John Doe,client1@example.com,Apex Retail,SEO & Content Growth,Review draft articles and approve Q3 keyword list,100,1
Sarah Jenkins,client2@example.com,Nexus Tech,Google Ads PPC,Bid strategy adjustments and search term audit in progress,100,1
Michael Chang,client3@example.com,Lumen City,Brand Identity & Creative,Final logo and typography guidelines ready for feedback,100,1
```

| Field | Description |
| :--- | :--- |
| `name` | Client contact person |
| `email` | Client recipient email address |
| `company` | Client business / brand name |
| `project_name` | Marketing scope or deliverable title |
| `reminder_note` | Work item / milestone note displayed prominently in the email |
| `daily_limit` | Maximum emails to send this client per 24 hours (default: `100`) |
| `is_active` | `1` to send regular reminders, `0` to pause this client |

---

### 3. Email Template Customization

Templates are stored in `templates/reminder.html` and `templates/reminder.txt`. The following dynamic placeholders are injected automatically:

| Tag | Injected Value |
| :--- | :--- |
| `{client_name}` | Contact name of the client |
| `{client_email}` | Recipient email address |
| `{company}` | Client organization / brand name |
| `{project_name}` | Marketing campaign or deliverable scope |
| `{reminder_note}` | Current milestone or action note |
| `{sequence_num}` | Transmission sequence number (e.g. `1` to `100`) |
| `{daily_limit}` | Daily quota limit (e.g. `100`) |
| `{current_date}` | Formatted date (e.g. `Nov 10, 2026`) |
| `{current_time}` | Formatted timestamp (e.g. `15:30:00`) |
| `{sender_name}` | Agency sender display name |
| `{sender_email}` | Agency sender email address |

---

## Headless CLI Commands (Optional for Servers / VPS)

For headless staging environments, Linux relays, or background servers where a desktop UI is not needed:

```bash
# Start 24/7 background dispatcher in terminal
python main.py start

# View real-time status table and 24h quotas
python main.py status

# Test Webmail connection & send a test reminder
python main.py test --recipient your_email@domain.com

# Re-sync clients.csv into SQLite database
python main.py sync
```

---

## Project Structure

```
MarketingMailer/
├── main.py                     # CLI and Desktop GUI entry router
├── desktop_launcher.pyw        # Console-less Windows application launcher
├── pyproject.toml              # Modern package metadata (PEP 517/621)
├── requirements.txt            # Python dependencies (customtkinter, pystray, pillow)
├── .env.example                # Configuration template
│
├── gui/                        # Modern Desktop Application
│   ├── app.py                  # Main window controller & 24/7 thread coordination
│   ├── theme.py                # Dark/Light theme design tokens & typography
│   ├── tray.py                 # Windows system tray minimization manager
│   └── views/                  # View modules
│       ├── dashboard.py        # KPI metric cards, master toggle, live feed
│       ├── clients.py          # Interactive client roster table & edit dialog
│       ├── template.py         # Live email preview & test send tool
│       └── settings.py         # Webmail SMTP configuration & connection tester
│
├── mailer/                     # Core Email & Rate Limiting Engine
│   ├── config.py               # Settings loader and environment manager
│   ├── database.py             # SQLite storage for rolling 24h limits & logs
│   ├── clients.py              # CSV/JSON client importer & synchronizer
│   ├── smtp_client.py          # Webmail SMTP client with auto-reconnect
│   ├── templates.py            # RFC 5322 MIME generator & template renderer
│   └── engine.py               # 24/7 round-robin scheduling loop
│
├── data/
│   ├── clients.csv             # 30 pre-loaded marketing client roster slots
│   └── mailer.db               # SQLite database (auto-created at runtime)
│
├── templates/
│   ├── reminder.html           # Responsive HTML work reminder template
│   └── reminder.txt            # Plain-text fallback template
│
├── assets/
│   ├── app_icon.ico            # Multi-resolution Windows executable icon
│   └── icon.png                # High-resolution application logo
│
├── scripts/
│   └── build_windows_exe.bat   # One-click PyInstaller standalone build script
│
└── tests/                      # Automated unit test suite
    ├── test_mailer.py          # Quotas, pacing, database, template tests
    └── test_gui.py             # GUI tokens, tray icon, lifecycle tests
```

---

## Running Automated Tests

A comprehensive unit test suite is included to verify rolling 24-hour quotas, pacing intervals, database integrity, and GUI design tokens:

```bash
python -m unittest discover -s tests
```

---

## License & Attribution

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.

- **Copyright &copy; 2026 bdchamp. All rights reserved.**
- Free for use, modification, and redistribution under the terms of the GPL-3.0.
- Any derivative works or public distributions must remain open source under the GPL-3.0 license and preserve original author attribution.

### Support & Contact
- **Author:** bdchamp
