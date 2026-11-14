@echo off
title Marketing Mailer Web Server (Localhost)
cd /d "%~dp0"

echo ===============================================================
echo      MARKETING MAILER - LOCALHOST WEB DASHBOARD
echo ===============================================================
echo.
echo  Opening browser at: http://localhost:8085
echo  Default Login:
echo    Username: admin
echo    Password: (from .env or admin123)
echo.
echo  [i] Press Ctrl+C at any time to stop the local web server.
echo ===============================================================
echo.

start "" "http://localhost:8085"
python run_web.py --port 8085 --host 127.0.0.1

pause

