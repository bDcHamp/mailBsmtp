#!/usr/bin/env pythonw
"""
Windows Desktop Launcher for Marketing SMTP Mailer.
Runs without opening a black CMD console window.
"""

import sys
from pathlib import Path

# Ensure root directory is on Python path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from gui.app import launch_gui

if __name__ == "__main__":
    launch_gui()

