@echo off
setlocal enabledelayedexpansion

echo ==============================================================
echo     Marketing SMTP Work Reminder System - One-Click Build
echo ==============================================================
echo.

cd /d "%~dp0\.."

echo [*] Checking Python environment...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python was not found in PATH. Please install Python 3.8+ and try again.
    pause
    exit /b 1
)

echo [*] Ensuring required packaging tools are installed...
python -m pip install --upgrade pip
python -m pip install customtkinter pystray pillow pyinstaller

echo.
echo [*] Compiling standalone Windows application (MarketingMailer.exe)...
echo     (This may take 1-2 minutes to package all dependencies...)
echo.

python -m PyInstaller ^
    --name="MarketingMailer" ^
    --noconsole ^
    --onedir ^
    --icon="assets/app_icon.ico" ^
    --add-data="templates;templates" ^
    --add-data="data;data" ^
    --add-data="assets;assets" ^
    --collect-all=customtkinter ^
    --hidden-import=PIL ^
    --hidden-import=pystray ^
    --hidden-import=sqlite3 ^
    --hidden-import=smtplib ^
    --clean ^
    --noconfirm ^
    desktop_launcher.pyw

if %errorlevel% neq 0 (
    echo.
    echo [!] Build failed. Please review the compilation errors above.
    pause
    exit /b %errorlevel%
)

echo [*] Copying default configuration files into output directory...
if not exist "dist\MarketingMailer\.env" (
    copy ".env.example" "dist\MarketingMailer\.env" >nul
)
if not exist "dist\MarketingMailer\data\clients.csv" (
    mkdir "dist\MarketingMailer\data" 2>nul
    copy "data\clients.csv" "dist\MarketingMailer\data\clients.csv" >nul
)

echo.
echo ==============================================================
echo [SUCCESS] Build Complete!
echo.
echo Your portable Windows Desktop application is located at:
echo   %CD%\dist\MarketingMailer\MarketingMailer.exe
echo.
echo Staff can double-click MarketingMailer.exe to run the app.
echo ==============================================================
echo.
pause

