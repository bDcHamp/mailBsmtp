"""
Web Application Routes and JSON APIs for Marketing Mailer.
"""

import csv
from datetime import datetime
from io import StringIO
import os
from pathlib import Path
from flask import (
    Blueprint,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from mailer.clients import parse_csv_stream, sync_clients
from mailer.config import BASE_DIR, Config
from mailer.database import (
    create_email_template,
    create_group,
    delete_client,
    delete_email_template,
    delete_group,
    duplicate_email_template,
    get_active_clients,
    get_all_clients,
    get_all_groups,
    get_all_templates,
    get_client_assigned_template_ids,
    get_client_summary_stats,
    get_group,
    get_template_by_id,
    set_client_assigned_templates,
    toggle_group_active,
    toggle_template_active,
    update_email_template,
    update_group,
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
    groups = get_all_groups(Config.DATABASE_PATH)
    templates = get_all_templates(Config.DATABASE_PATH)
    active_count = sum(1 for s in stats if s["is_active"])
    total_sent = sum(s["sent_24h"] for s in stats)
    total_remaining = sum(s["remaining_quota"] for s in stats if s["is_active"])

    return render_template(
        "dashboard.html",
        active_tab="dashboard",
        is_running=engine_manager.is_running,
        active_clients=active_count,
        total_clients=len(stats),
        total_groups=len(groups),
        total_templates=len(templates),
        total_sent=total_sent,
        total_remaining=total_remaining,
        smtp_host=Config.SMTP_HOST,
        smtp_port=Config.SMTP_PORT,
    )


@main_bp.route("/clients")
@login_required
def clients():
    stats = get_client_summary_stats(Config.DATABASE_PATH, Config.WINDOW_HOURS)
    groups = get_all_groups(Config.DATABASE_PATH)
    templates = get_all_templates(Config.DATABASE_PATH)
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
            "group_id": s.get("group_id"),
            "group_name": s.get("group_name"),
            "group_is_active": s.get("group_is_active", 1),
            "rotation_interval_minutes": s.get("rotation_interval_minutes", 0),
            "assigned_template_ids": s.get("assigned_template_ids", []),
        })

    return render_template(
        "clients.html",
        active_tab="clients",
        clients=enriched,
        groups=groups,
        templates=templates,
    )


@main_bp.route("/template")
@login_required
def template_view():
    active_clients = get_active_clients(Config.DATABASE_PATH)
    templates = get_all_templates(Config.DATABASE_PATH)
    return render_template(
        "template.html",
        active_tab="template",
        clients=active_clients,
        templates=templates,
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
    groups = get_all_groups(Config.DATABASE_PATH)
    templates = get_all_templates(Config.DATABASE_PATH)
    active_count = sum(1 for s in stats if s["is_active"])
    total_sent = sum(s["sent_24h"] for s in stats)
    total_remaining = sum(s["remaining_quota"] for s in stats if s["is_active"])

    return jsonify({
        "is_running": engine_manager.is_running,
        "active_clients": active_count,
        "total_clients": len(stats),
        "total_groups": len(groups),
        "total_templates": len(templates),
        "total_sent": total_sent,
        "total_remaining": total_remaining,
        "smtp_host": Config.SMTP_HOST,
        "smtp_port": Config.SMTP_PORT,
    })


@main_bp.route("/api/engine/toggle", methods=["POST"])
@login_required
def api_engine_toggle():
    try:
        if engine_manager.is_running:
            engine_manager.stop()
        else:
            engine_manager.start()
        return jsonify({"success": True, "is_running": engine_manager.is_running})
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(exc)}), 500


@main_bp.route("/api/engine/logs")
@login_required
def api_engine_logs():
    logs = engine_manager.get_logs(limit=50)
    return jsonify({"logs": logs})


# -------------------------------------------------------------
# Group APIs
# -------------------------------------------------------------

@main_bp.route("/api/groups", methods=["GET"])
@login_required
def api_groups_list():
    groups = get_all_groups(Config.DATABASE_PATH)
    return jsonify({"success": True, "groups": groups})


@main_bp.route("/api/groups/create", methods=["POST"])
@login_required
def api_group_create():
    data = request.json or request.form
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Group name is required"}), 400
    try:
        gid = create_group(name, description, Config.DATABASE_PATH)
        return jsonify({"success": True, "group_id": gid, "message": f"Group '{name}' created"})
    except Exception as e:
        return jsonify({"success": False, "error": f"Could not create group (name may already exist): {str(e)}"}), 400


@main_bp.route("/api/groups/update", methods=["POST"])
@login_required
def api_group_update():
    data = request.json or request.form
    try:
        group_id = int(data.get("group_id"))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid group ID"}), 400
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Group name is required"}), 400

    update_group(group_id, name, description, Config.DATABASE_PATH)
    return jsonify({"success": True, "message": "Group updated"})


@main_bp.route("/api/groups/toggle", methods=["POST"])
@login_required
def api_group_toggle():
    data = request.json or request.form
    try:
        group_id = int(data.get("group_id"))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid group ID"}), 400

    new_state = toggle_group_active(group_id, Config.DATABASE_PATH)
    return jsonify({"success": True, "is_active": new_state})


@main_bp.route("/api/groups/delete", methods=["POST"])
@login_required
def api_group_delete():
    data = request.json or request.form
    try:
        group_id = int(data.get("group_id"))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid group ID"}), 400
    delete_clients = data.get("delete_clients", False) in (True, "true", 1, "1")

    delete_group(group_id, delete_clients, Config.DATABASE_PATH)
    return jsonify({"success": True, "message": "Group deleted"})


# -------------------------------------------------------------
# Email Templates Studio APIs
# -------------------------------------------------------------

@main_bp.route("/api/templates", methods=["GET"])
@login_required
def api_templates_list():
    templates = get_all_templates(Config.DATABASE_PATH)
    return jsonify({"success": True, "templates": templates})


@main_bp.route("/api/templates/create", methods=["POST"])
@login_required
def api_template_create():
    data = request.json or request.form
    name = data.get("name", "").strip()
    subject = data.get("subject", "").strip()
    html_content = data.get("html_content", "").strip()
    text_content = data.get("text_content", "").strip()
    is_active = 1 if data.get("is_active", True) in (True, 1, "1", "true") else 0

    if not name:
        return jsonify({"success": False, "error": "Template name is required"}), 400
    if not subject:
        return jsonify({"success": False, "error": "Email subject line is required"}), 400
    if not html_content and not text_content:
        return jsonify({"success": False, "error": "Please provide HTML or plain text body"}), 400

    try:
        tid = create_email_template(
            name=name,
            subject=subject,
            html_content=html_content or f"<pre>{text_content}</pre>",
            text_content=text_content or html_content,
            is_active=is_active,
            db_path=Config.DATABASE_PATH,
        )
        return jsonify({"success": True, "template_id": tid, "message": f"Template '{name}' created"})
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to create template (name must be unique): {str(e)}"}), 400


@main_bp.route("/api/templates/<int:template_id>", methods=["GET"])
@login_required
def api_template_get(template_id: int):
    t = get_template_by_id(template_id, Config.DATABASE_PATH)
    if not t:
        return jsonify({"success": False, "error": "Template not found"}), 404
    return jsonify({"success": True, "template": t})


@main_bp.route("/api/templates/update", methods=["POST"])
@login_required
def api_template_update():
    data = request.json or request.form
    try:
        template_id = int(data.get("template_id"))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid template ID"}), 400

    name = data.get("name", "").strip()
    subject = data.get("subject", "").strip()
    html_content = data.get("html_content", "").strip()
    text_content = data.get("text_content", "").strip()
    is_active = 1 if data.get("is_active", True) in (True, 1, "1", "true") else 0

    if not name or not subject:
        return jsonify({"success": False, "error": "Template name and subject are required"}), 400

    try:
        update_email_template(
            template_id=template_id,
            name=name,
            subject=subject,
            html_content=html_content or f"<pre>{text_content}</pre>",
            text_content=text_content or html_content,
            is_active=is_active,
            db_path=Config.DATABASE_PATH,
        )
        return jsonify({"success": True, "message": "Template updated successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to update template: {str(e)}"}), 400


@main_bp.route("/api/templates/toggle", methods=["POST"])
@login_required
def api_template_toggle():
    data = request.json or request.form
    try:
        template_id = int(data.get("template_id"))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid template ID"}), 400

    new_state = toggle_template_active(template_id, Config.DATABASE_PATH)
    return jsonify({"success": True, "is_active": new_state})


@main_bp.route("/api/templates/duplicate", methods=["POST"])
@login_required
def api_template_duplicate():
    data = request.json or request.form
    try:
        template_id = int(data.get("template_id"))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid template ID"}), 400

    new_tid = duplicate_email_template(template_id, Config.DATABASE_PATH)
    if new_tid:
        return jsonify({"success": True, "template_id": new_tid, "message": "Template duplicated successfully"})
    return jsonify({"success": False, "error": "Failed to duplicate template"}), 404


@main_bp.route("/api/templates/delete", methods=["POST"])
@login_required
def api_template_delete():
    data = request.json or request.form
    try:
        template_id = int(data.get("template_id"))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid template ID"}), 400

    deleted = delete_email_template(template_id, Config.DATABASE_PATH)
    if deleted:
        return jsonify({"success": True, "message": "Template deleted successfully"})
    return jsonify({"success": False, "error": "Failed to delete template"}), 404


@main_bp.route("/api/clients/<client_id>/templates", methods=["GET"])
@login_required
def api_client_get_templates(client_id: str):
    tids = get_client_assigned_template_ids(client_id, Config.DATABASE_PATH)
    return jsonify({"success": True, "template_ids": tids})


@main_bp.route("/api/clients/assign-templates", methods=["POST"])
@login_required
def api_client_assign_templates():
    data = request.json or request.form
    client_id = data.get("client_id", "").strip().lower()
    if not client_id:
        return jsonify({"success": False, "error": "Client ID required"}), 400

    raw_tids = data.get("template_ids", [])
    if isinstance(raw_tids, str):
        tids = [int(x.strip()) for x in raw_tids.split(",") if x.strip().isdigit()]
    elif isinstance(raw_tids, list):
        tids = [int(x) for x in raw_tids if str(x).isdigit()]
    else:
        tids = []

    set_client_assigned_templates(client_id, tids, Config.DATABASE_PATH)
    return jsonify({"success": True, "message": "Assigned templates updated"})


# -------------------------------------------------------------
# Client CRUD & File Handling APIs
# -------------------------------------------------------------

@main_bp.route("/api/clients/add", methods=["POST"])
@login_required
def api_client_add():
    data = request.json or request.form
    email = data.get("email", "").strip()
    if not email or "@" not in email:
        return jsonify({"success": False, "error": "Invalid email address"}), 400

    group_id = data.get("group_id")
    if group_id in ("", None, "null", "None", "ungrouped"):
        group_id = None
    else:
        try:
            group_id = int(group_id)
        except (ValueError, TypeError):
            group_id = None

    rot_interval = data.get("rotation_interval_minutes", 0)
    try:
        rot_interval = int(rot_interval)
    except (ValueError, TypeError):
        rot_interval = 0

    # Parse template_ids if provided
    raw_tids = data.get("template_ids")
    template_ids = None
    if raw_tids is not None:
        if isinstance(raw_tids, str):
            template_ids = [int(x.strip()) for x in raw_tids.split(",") if x.strip().isdigit()]
        elif isinstance(raw_tids, list):
            template_ids = [int(x) for x in raw_tids if str(x).isdigit()]

    client_data = {
        "client_id": email.lower(),
        "name": data.get("name", "").strip() or email.split("@")[0].title(),
        "email": email,
        "company": data.get("company", "").strip(),
        "project_name": data.get("project_name", "").strip() or "Marketing Campaign",
        "reminder_note": data.get("reminder_note", "").strip() or "Regular work progress reminder.",
        "daily_limit": int(data.get("daily_limit", 100)),
        "is_active": 1 if data.get("is_active", True) in (True, 1, "1", "true") else 0,
        "group_id": group_id,
        "rotation_interval_minutes": rot_interval,
    }
    if template_ids is not None:
        client_data["template_ids"] = template_ids

    upsert_client(client_data, Config.DATABASE_PATH)
    return jsonify({"success": True})


@main_bp.route("/api/clients/update", methods=["POST"])
@login_required
def api_client_update():
    return api_client_add()


@main_bp.route("/api/clients/delete", methods=["POST"])
@login_required
def api_client_delete():
    data = request.json or request.form
    client_id = data.get("client_id", "").strip().lower()
    if not client_id:
        return jsonify({"success": False, "error": "Client ID required"}), 400

    deleted = delete_client(client_id, Config.DATABASE_PATH)
    if deleted:
        return jsonify({"success": True, "message": "Client deleted successfully"})
    return jsonify({"success": False, "error": "Client not found or could not be deleted"}), 404


@main_bp.route("/api/clients/bulk-delete", methods=["POST"])
@login_required
def api_clients_bulk_delete():
    data = request.json or request.form
    client_ids = data.get("client_ids", [])
    if isinstance(client_ids, str):
        client_ids = [c.strip().lower() for c in client_ids.split(",") if c.strip()]
    count = 0
    for cid in client_ids:
        if delete_client(cid, Config.DATABASE_PATH):
            count += 1
    return jsonify({"success": True, "count": count})


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


@main_bp.route("/api/clients/upload-csv", methods=["POST"])
@login_required
def api_client_upload_csv():
    """Accept multipart CSV file upload and bulk import into SQLite."""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "Empty filename"}), 400

    group_id = request.form.get("group_id")
    if group_id in ("", None, "null", "all", "ungrouped"):
        target_group_id = None
    else:
        try:
            target_group_id = int(group_id)
        except ValueError:
            target_group_id = None

    try:
        content = file.stream.read().decode("utf-8-sig", errors="ignore")
        stream = StringIO(content)
        clients_list, skipped = parse_csv_stream(stream, default_group_id=target_group_id)

        imported = 0
        for c in clients_list:
            upsert_client(c, Config.DATABASE_PATH)
            imported += 1

        return jsonify({
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "message": f"Successfully imported {imported} clients ({skipped} skipped/invalid)."
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to parse CSV: {str(e)}"}), 500


@main_bp.route("/api/clients/export-csv")
@login_required
def api_clients_export_csv():
    """Export clients to a CSV download, optionally filtered by group_id."""
    group_id = request.args.get("group_id")
    target_group_id = None
    if group_id and group_id not in ("all", "null", ""):
        try:
            target_group_id = int(group_id)
        except ValueError:
            pass

    clients = get_all_clients(Config.DATABASE_PATH, group_id=target_group_id)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "email", "company", "project_name", "reminder_note", "daily_limit", "is_active", "group_name"])
    for c in clients:
        writer.writerow([
            c["name"],
            c["email"],
            c.get("company", ""),
            c.get("project_name", ""),
            c.get("reminder_note", ""),
            c.get("daily_limit", 100),
            c.get("is_active", 1),
            c.get("group_name", "") or "Ungrouped",
        ])

    filename = f"clients_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@main_bp.route("/api/clients/sync-csv", methods=["POST"])
@login_required
def api_clients_sync_csv():
    count = sync_clients(Config.DATABASE_PATH, Config.CLIENTS_CSV_PATH, Config.CLIENTS_JSON_PATH)
    return jsonify({"success": True, "count": count})


# -------------------------------------------------------------
# Template Render & Test Send APIs
# -------------------------------------------------------------

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

    template_id = request.args.get("template_id")
    template_data = None
    if template_id and template_id.isdigit():
        template_data = get_template_by_id(int(template_id), Config.DATABASE_PATH)

    subject_prefix = request.args.get("subject", Config.EMAIL_SUBJECT)
    msg = create_reminder_message(
        client=client,
        sequence_num=1,
        sender_name=Config.SENDER_NAME,
        sender_email=Config.SENDER_EMAIL,
        subject_prefix=subject_prefix,
        html_template_path=Config.HTML_TEMPLATE_PATH,
        text_template_path=Config.TEXT_TEMPLATE_PATH,
        template_data=template_data,
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
        "template_id": template_data["id"] if template_data else None,
        "template_name": template_data["name"] if template_data else "Default",
    })


@main_bp.route("/api/template/send-test", methods=["POST"])
@login_required
def api_template_send_test():
    data = request.json or request.form
    recipient = data.get("recipient", "").strip()
    client_id = data.get("client_id", "").strip()
    template_id = data.get("template_id")
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

    template_data = None
    if template_id and str(template_id).isdigit():
        template_data = get_template_by_id(int(template_id), Config.DATABASE_PATH)

    msg = create_reminder_message(
        client=client,
        sequence_num=1,
        sender_name=Config.SENDER_NAME,
        sender_email=Config.SENDER_EMAIL,
        subject_prefix=subject,
        html_template_path=Config.HTML_TEMPLATE_PATH,
        text_template_path=Config.TEXT_TEMPLATE_PATH,
        template_data=template_data,
    )

    ok, err = engine_manager.engine.smtp_client.send_email(Config.SENDER_EMAIL, recipient, msg)
    if ok:
        return jsonify({"success": True, "message": f"Preview email delivered to {recipient}!"})
    else:
        return jsonify({"success": False, "error": err}), 500


# -------------------------------------------------------------
# Settings APIs
# -------------------------------------------------------------

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
AUTO_START_ENGINE=false
"""
    env_path = BASE_DIR / ".env"
    try:
        env_path.write_text(env_content, encoding="utf-8")
        return jsonify({"success": True, "message": "Settings saved successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
