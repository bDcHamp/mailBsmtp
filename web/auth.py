"""
Authentication and session management for Marketing Mailer Web.
"""

from functools import wraps
import os
from flask import flash, jsonify, redirect, request, session, url_for

from mailer.config import Config


def get_admin_credentials():
    """Retrieve web login credentials from environment or defaults."""
    username = os.getenv("WEB_ADMIN_USER", "admin")
    password = os.getenv("WEB_ADMIN_PASSWORD", "admin123")
    return username, password


def login_required(f):
    """Decorator ensuring routes are accessible only by authenticated staff."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Unauthorized"}), 401
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

