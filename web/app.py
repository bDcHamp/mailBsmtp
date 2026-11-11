"""
Flask Application Factory for Marketing Mailer Web.
"""

import os
from pathlib import Path
from flask import Flask

from mailer.clients import sync_clients
from mailer.config import Config
from mailer.database import init_db
from web.engine_service import engine_manager
from web.routes import auth_bp, main_bp


def create_app(config_overrides: dict = None) -> Flask:
    """Initialize and configure the Flask web application."""
    app_dir = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(app_dir / "templates"),
        static_folder=str(app_dir / "static"),
    )

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "marketing-mailer-session-key-2026")
    if config_overrides:
        app.config.update(config_overrides)

    # Initialize local SQLite database and sync clients
    init_db(Config.DATABASE_PATH)
    sync_clients(Config.DATABASE_PATH, Config.CLIENTS_CSV_PATH, Config.CLIENTS_JSON_PATH)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    # Check if auto-start engine on boot is requested
    if os.getenv("AUTO_START_ENGINE", "false").lower() in ("1", "true", "yes"):
        engine_manager.start()

    return app

