"""
Email templating and message composition.
Loads HTML/text templates and generates RFC 5322 compliant MIME messages.
"""

from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Any, Dict


def load_file_content(path: Path, fallback_content: str) -> str:
    """Read template file content with fallback."""
    if path.is_file():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            pass
    return fallback_content


FALLBACK_HTML = """<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
  <h2>Work Progress Reminder: {project_name}</h2>
  <p>Dear {client_name},</p>
  <p>This is a scheduled work update regarding your marketing campaign with {company}.</p>
  <div style="background: #f4f6f9; padding: 15px; border-left: 4px solid #0056b3; margin: 15px 0;">
    <strong>Milestone Note:</strong> {reminder_note}
  </div>
  <p>Sequence #{sequence_num} of {daily_limit}. Date: {current_date} {current_time}.</p>
  <p>Best regards,<br><strong>{sender_name}</strong></p>
</body>
</html>"""

FALLBACK_TEXT = """Work Progress Reminder: {project_name}
Dear {client_name},

This is a scheduled work update regarding your marketing campaign with {company}.

Milestone Note:
{reminder_note}

Sequence #{sequence_num} of {daily_limit}. Date: {current_date} {current_time}.
Best regards,
{sender_name}
"""


def render_string(template_str: str, context: Dict[str, Any]) -> str:
    """Format template string safely with dictionary context."""
    # Use standard str.format with a safe fallback
    class SafeDict(dict):
        def __missing__(self, key):
            return f"{{{key}}}"

    return template_str.format_map(SafeDict(**context))


def create_reminder_message(
    client: Dict[str, Any],
    sequence_num: int,
    sender_name: str,
    sender_email: str,
    subject_prefix: str,
    html_template_path: Path,
    text_template_path: Path,
) -> MIMEMultipart:
    """
    Construct a complete, RFC-compliant multipart MIME email.
    """
    now = datetime.now()
    context = {
        "client_name": client.get("name", "Valued Client"),
        "client_email": client.get("email", ""),
        "company": client.get("company", "Client Partner"),
        "project_name": client.get("project_name", "Marketing Campaign"),
        "reminder_note": client.get("reminder_note", "Regular campaign deliverable monitoring."),
        "sequence_num": sequence_num,
        "daily_limit": client.get("daily_limit", 100),
        "current_date": now.strftime("%b %d, %Y"),
        "current_time": now.strftime("%H:%M:%S"),
        "sender_name": sender_name,
        "sender_email": sender_email,
    }

    # Load and render template bodies
    html_raw = load_file_content(html_template_path, FALLBACK_HTML)
    text_raw = load_file_content(text_template_path, FALLBACK_TEXT)

    rendered_html = render_string(html_raw, context)
    rendered_text = render_string(text_raw, context)

    # Compose MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{subject_prefix} - {context['project_name']} [#{sequence_num}]"
    msg["From"] = f'"{sender_name}" <{sender_email}>'
    msg["To"] = f'"{context["client_name"]}" <{context["client_email"]}>'
    msg["Date"] = formatdate(localtime=True)

    # Determine domain for Message-ID
    sender_domain = sender_email.split("@")[-1] if "@" in sender_email else "localhost"
    msg["Message-ID"] = make_msgid(domain=sender_domain)

    # Email client & delivery headers
    msg["X-Mailer"] = "Marketing-Client-Reminder-System/2.0"
    msg["Precedence"] = "bulk"
    msg["Auto-Submitted"] = "auto-generated"

    # Attach plain-text first, then HTML (email clients prefer last part)
    msg.attach(MIMEText(rendered_text, "plain", "utf-8"))
    msg.attach(MIMEText(rendered_html, "html", "utf-8"))

    return msg

