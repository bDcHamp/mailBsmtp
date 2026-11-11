"""
Web Application Routes and JSON APIs for Marketing Mailer.
"""

from datetime import datetime
import os
from pathlib import Path
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from mailer.clients import sync_clients
from mailer.config import BASE_DIR, Config
from mailer.database import (
    get_active_clients,
    get_all_clients,
    get_client_summary_stats,
    upsert_client,
)
from mailer.smtp_client import SMTPClient
from mailer.templates import create_reminder_message
from web.auth import get_admin_credentials, login_required
from web.engine_service import engine_manager

auth_bp = Blueprint("auth", __name__)
main_bp = Blueprint("main", __name__)


# -------------------------------------------------------------
# Authentication Routes
# -------------------------------------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("main.dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        admin_user, admin_pass = get_admin_credentials()

        if username == admin_user and password == admin_pass:
            session["logged_in"] = True
            session["username"] = username
            next_url = request.args.get("next") or url_for("main.dashboard")
            return redirect(next_url)
        else:
            error = "Invalid username or password. Please try again."

    return render_template("login.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


# -------------------------------------------------------------
# Page Views (Protected)
# -------------------------------------------------------------

@main_bp.route("/")
@login_required
def dashboard():
    stats = get_client_summary_stats(Config.DATABASE_PATH, Config.WINDOW_HOURS)
    active_count = sum(1 for s in stats if s["is_active"])
    total_sent = sum(s["sent_24h"] for s in stats)
    total_remaining = sum(s["remaining_quota"] for s in stats if s["is_active"])

    return render_template(
        "dashboard.html",
        active_tab="dashboard",
        is_running=engine_manager.is_running,
        active_clients=active_count,
        total_sent=total_sent,
        total_remaining=total_remaining,
        smtp_host=Config.SMTP_HOST,
        smtp_port=Config.SMTP_PORT,
    )


@main_bp.route("/clients")
@login_required
def clients():
    stats = get_client_summary_stats(Config.DATABASE_PATH, Config.WINDOW_HOURS)
    all_clients_map = {c["client_id"]: c for c in get_all_clients(Config.DATABASE_PATH)}

    enriched = []
    for s in stats:
        cid = s["client_id"]
        c_record = all_clients_map.get(cid, {})
        enriched.append({
            "client_id": cid,
            "name": s["name"],
            "email": s["email"],
            "company": s["company"],
            "project_name": c_record.get("project_name", "Marketing Campaign"),
            "reminder_note": c_record.get("reminder_note", "Regular work progress reminder."),
            "daily_limit": s["daily_limit"],
            "sent_24h": s["sent_24h"],
            "remaining_quota": s["remaining_quota"],
            "is_active": s["is_active"],
            "last_sent": s["last_sent"],
        })

    return render_template("clients.html", active_tab="clients", clients=enriched)


@main_bp.route("/template")
@login_required
def template_view():
    active_clients = get_active_clients(Config.DATABASE_PATH)
    return render_template(
        "template.html",
        active_tab="template",
        clients=active_clients,
        default_subject=Config.EMAIL_SUBJECT,
    )


@main_bp.route("/settings")
@login_required
def settings_view():
    return render_template(
        "settings.html",
        active_tab="settings",
        config=Config,
    )


# -------------------------------------------------------------
# JSON APIs (Protected)
# -------------------------------------------------------------

@main_bp.route("/api/stats")
@login_required
def api_stats():
    stats = get_client_summary_stats(Config.DATABASE_PATH, Config.WINDOW_HOURS)
    active_count = sum(1 for s in stats if s["is_active"])
    total_sent = sum(s["sent_24h"] for s in stats)
    total_remaining = sum(s["remaining_quota"] for s in stats if s["is_active"])

    return jsonify({
        "is_running": engine_manager.is_running,
        "active_clients": active_count,
        "total_sent": total_sent,
        "total_remaining": total_remaining,
        "smtp_host": Config.SMTP_HOST,
        "smtp_port": Config.SMTP_PORT,
    })


@main_bp.route("/api/engine/toggle", methods=["POST"])
@login_required
def api_engine_toggle():
    if engine_manager.is_running:
        engine_manager.stop()
    else:
        engine_manager.start()
    return jsonify({"success": True, "is_running": engine_manager.is_running})


@main_bp.route("/api/engine/logs")
@login_required
def api_engine_logs():
    logs = engine_manager.get_logs(limit=50)
    return jsonify({"logs": logs})


@main_bp.route("/api/clients/add", methods=["POST"])
@login_required
def api_client_add():
    data = request.json or request.form
    email = data.get("email", "").strip()
    if not email or "@" not in email:
        return jsonify({"success": False, "error": "Invalid email address"}), 400

    client_data = {
        "client_id": email.lower(),
        "name": data.get("name", "").strip() or email.split("@")[0].title(),
        "email": email,
        "company": data.get("company", "").strip(),
        "project_name": data.get("project_name", "").strip() or "Marketing Campaign",
        "reminder_note": data.get("reminder_note", "").strip() or "Regular work progress reminder.",
        "daily_limit": int(data.get("daily_limit", 100)),
        "is_active": 1 if data.get("is_active", True) in (True, 1, "1", "true") else 0,
    }
    upsert_client(client_data, Config.DATABASE_PATH)
    return jsonify({"success": True})


@main_bp.route("/api/clients/update", methods=["POST"])
@login_required
def api_client_update():
    return api_client_add()


@main_bp.route("/api/clients/toggle-active", methods=["POST"])
@login_required
def api_client_toggle_active():
    data = request.json or request.form
    client_id = data.get("client_id", "").strip().lower()
    all_clients = get_all_clients(Config.DATABASE_PATH)
    client_rec = next((c for c in all_clients if c["client_id"] == client_id), None)

    if not client_rec:
        return jsonify({"success": False, "error": "Client not found"}), 404

    client_rec["is_active"] = 0 if client_rec["is_active"] else 1
    upsert_client(client_rec, Config.DATABASE_PATH)
    return jsonify({"success": True, "is_active": bool(client_rec["is_active"])})


@main_bp.route("/api/clients/sync-csv", methods=["POST"])
@login_required
def api_clients_sync_csv():
    count = sync_clients(Config.DATABASE_PATH, Config.CLIENTS_CSV_PATH, Config.CLIENTS_JSON_PATH)
    return jsonify({"success": True, "count": count})


@main_bp.route("/api/template/render")
@login_required
def api_template_render():
    client_id = request.args.get("client_id", "")
    all_c = get_all_clients(Config.DATABASE_PATH)
    client = next((c for c in all_c if c["client_id"] == client_id), None)

    if not client:
        client = {
            "name": "Valued Client",
            "email": "client@example.com",
            "company": "Apex Partner",
            "project_name": "Digital Marketing Strategy",
            "reminder_note": "Deliverables review and Q3 campaign milestone update.",
            "daily_limit": 100,
        }

    subject_prefix = request.args.get("subject", Config.EMAIL_SUBJECT)
    msg = create_reminder_message(
        client=client,
        sequence_num=1,
        sender_name=Config.SENDER_NAME,
        sender_email=Config.SENDER_EMAIL,
        subject_prefix=subject_prefix,
        html_template_path=Config.HTML_TEMPLATE_PATH,
        text_template_path=Config.TEXT_TEMPLATE_PATH,
    )

    rendered_text = ""
    rendered_html = ""
    for part in msg.walk():
        ct = part.get_content_type()
        if ct == "text/plain":
            rendered_text = part.get_payload(decode=True).decode("utf-8", errors="ignore")
        elif ct == "text/html":
            rendered_html = part.get_payload(decode=True).decode("utf-8", errors="ignore")

    return jsonify({
        "subject": msg["Subject"],
        "from": msg["From"],
        "to": msg["To"],
        "date": msg["Date"],
        "text": rendered_text,
        "html": rendered_html,
    })


@main_bp.route("/api/template/send-test", methods=["POST"])
@login_required
def api_template_send_test():
    data = request.json or request.form
    recipient = data.get("recipient", "").strip()
    client_id = data.get("client_id", "").strip()
    subject = data.get("subject", Config.EMAIL_SUBJECT).strip()

    if not recipient or "@" not in recipient:
        return jsonify({"success": False, "error": "Invalid recipient email"}), 400

    all_c = get_all_clients(Config.DATABASE_PATH)
    client = next((c for c in all_c if c["client_id"] == client_id), None)
    if not client:
        client = {
            "name": "Staff Preview",
            "email": recipient,
            "company": "Marketing Agency",
            "project_name": "Campaign Preview",
            "reminder_note": "Preview verification of reminder styling and Webmail relay.",
            "daily_limit": 100,
        }
    else:
        client = client.copy()
        client["email"] = recipient

    msg = create_reminder_message(
        client=client,
        sequence_num=1,
        sender_name=Config.SENDER_NAME,
        sender_email=Config.SENDER_EMAIL,
        subject_prefix=subject,
        html_template_path=Config.HTML_TEMPLATE_PATH,
        text_template_path=Config.TEXT_TEMPLATE_PATH,
    )

    ok, err = engine_manager.engine.smtp_client.send_email(Config.SENDER_EMAIL, recipient, msg)
    if ok:
        return jsonify({"success": True, "message": f"Preview email delivered to {recipient}!"})
    else:
        return jsonify({"success": False, "error": err}), 500


@main_bp.route("/api/settings/test-smtp", methods=["POST"])
@login_required
def api_settings_test_smtp():
    data = request.json or request.form
    host = data.get("host", Config.SMTP_HOST).strip()
    try:
        port = int(data.get("port", Config.SMTP_PORT))
    except ValueError:
        port = 465
    user = data.get("user", Config.SMTP_USER).strip()
    pwd = data.get("password", Config.SMTP_PASSWORD).strip()
    use_ssl = data.get("use_ssl", True) in (True, "true", "1", 1)
    use_tls = data.get("use_tls", False) in (True, "true", "1", 1)

    client = SMTPClient(
        host=host,
        port=port,
        username=user,
        password=pwd,
        use_ssl=use_ssl,
        use_tls=use_tls,
        timeout=15,
    )
    ok, msg = client.test_connection()
    if ok:
        return jsonify({"success": True, "message": msg})
    else:
        return jsonify({"success": False, "error": msg})


@main_bp.route("/api/settings/save", methods=["POST"])
@login_required
def api_settings_save():
    data = request.json or request.form
    host = data.get("host", Config.SMTP_HOST).strip()
    port = data.get("port", str(Config.SMTP_PORT)).strip()
    user = data.get("user", Config.SMTP_USER).strip()
    pwd = data.get("password", Config.SMTP_PASSWORD).strip()
    use_ssl = data.get("use_ssl", True) in (True, "true", "1", 1)
    use_tls = data.get("use_tls", False) in (True, "true", "1", 1)

    s_name = data.get("sender_name", Config.SENDER_NAME).strip() or "Marketing Operations Team"
    s_email = data.get("sender_email", Config.SENDER_EMAIL).strip() or user

    daily_cap = data.get("daily_cap", str(Config.DAILY_CAP_PER_CLIENT)).strip()
    delay = data.get("delay", str(Config.GLOBAL_DISPATCH_DELAY)).strip()

    # Update in-memory Config
    Config.SMTP_HOST = host
    Config.SMTP_PORT = int(port)
    Config.SMTP_USER = user
    Config.SMTP_PASSWORD = pwd
    Config.SMTP_USE_SSL = use_ssl
    Config.SMTP_USE_TLS = use_tls
    Config.SENDER_NAME = s_name
    Config.SENDER_EMAIL = s_email
    Config.DAILY_CAP_PER_CLIENT = int(daily_cap)
    Config.GLOBAL_DISPATCH_DELAY = float(delay)

    # Update engine SMTP client
    engine_manager.engine.smtp_client = SMTPClient(
        host=Config.SMTP_HOST,
        port=Config.SMTP_PORT,
        username=Config.SMTP_USER,
        password=Config.SMTP_PASSWORD,
        use_ssl=Config.SMTP_USE_SSL,
        use_tls=Config.SMTP_USE_TLS,
    )

    # Persist to .env
    env_content = f"""# Marketing Mailer Webmail Settings
SMTP_HOST={host}
SMTP_PORT={port}
SMTP_USER={user}
SMTP_PASSWORD={pwd}
SMTP_USE_SSL={'true' if use_ssl else 'false'}
SMTP_USE_TLS={'true' if use_tls else 'false'}

SENDER_NAME={s_name}
SENDER_EMAIL={s_email}

DAILY_CAP_PER_CLIENT={daily_cap}
WINDOW_HOURS=24.0
GLOBAL_DISPATCH_DELAY={delay}

# Web Dashboard Authentication
WEB_ADMIN_USER={os.getenv('WEB_ADMIN_USER', 'admin')}
WEB_ADMIN_PASSWORD={os.getenv('WEB_ADMIN_PASSWORD', 'admin123')}
"""
    env_path = BASE_DIR / ".env"
    try:
        env_path.write_text(env_content, encoding="utf-8")
        return jsonify({"success": True, "message": "Settings saved successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

