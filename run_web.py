#!/usr/bin/env python3
"""
Marketing Mailer Web Application Launcher.
Suitable for local testing and Contabo Linux VPS production hosting.
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure root directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from web.app import create_app
from web.auth import get_admin_credentials


def main():
    parser = argparse.ArgumentParser(description="Marketing Mailer Web Server")
    parser.add_argument("-p", "--port", type=int, default=int(os.getenv("PORT", "8085")), help="Port to listen on (default: 8085)")
    parser.add_argument("-H", "--host", default=os.getenv("HOST", "0.0.0.0"), help="Host IP to bind (default: 0.0.0.0)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")

    args = parser.parse_args()

    app = create_app()
    admin_user, admin_pass = get_admin_credentials()

    print("=" * 70)
    print("      MARKETING MAILER - WEB DASHBOARD SERVER")
    print("=" * 70)
    print(f" URL             : http://{args.host}:{args.port}")
    print(f" Internal Port   : {args.port} (Ideal for Contabo Nginx reverse proxy)")
    print(f" Admin Username  : {admin_user}")
    print(f" Admin Password  : {'*' * len(admin_pass)} (Configured via WEB_ADMIN_PASSWORD)")
    print("=" * 70)
    print(" [i] Press Ctrl+C to halt the web server.\n")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()

