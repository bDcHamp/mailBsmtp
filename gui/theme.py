"""
Theme and Styling System for Marketing Mailer Desktop App.
Provides clean dark/light color palettes, typography, and visual tokens.
"""

import customtkinter as ctk

# Color Palettes (Dark and Light)
COLORS = {
    "dark": {
        "bg": "#0f172a",          # Slate 900
        "card": "#1e293b",        # Slate 800
        "card_alt": "#334155",    # Slate 700
        "border": "#334155",      # Slate 700
        "text_primary": "#f8fafc",# Slate 50
        "text_muted": "#94a3b8",  # Slate 400
        "accent": "#3b82f6",      # Blue 500
        "accent_hover": "#2563eb",# Blue 600
        "success": "#10b981",     # Emerald 500
        "success_bg": "#064e3b",  # Dark Emerald
        "danger": "#ef4444",      # Red 500
        "danger_hover": "#dc2626",# Red 600
        "warning": "#f59e0b",     # Amber 500
    },
    "light": {
        "bg": "#f1f5f9",          # Slate 100
        "card": "#ffffff",        # Pure White
        "card_alt": "#f8fafc",    # Slate 50
        "border": "#e2e8f0",      # Slate 200
        "text_primary": "#0f172a",# Slate 900
        "text_muted": "#64748b",  # Slate 500
        "accent": "#2563eb",      # Blue 600
        "accent_hover": "#1d4ed8",# Blue 700
        "success": "#16a34a",     # Green 600
        "success_bg": "#dcfce7",  # Light Green
        "danger": "#dc2626",      # Red 600
        "danger_hover": "#b91c1c",# Red 700
        "warning": "#d97706",     # Amber 600
    }
}

FONTS = {
    "app_title": ("Segoe UI", 18, "bold"),
    "section_title": ("Segoe UI", 15, "bold"),
    "card_title": ("Segoe UI", 11, "bold"),
    "metric_value": ("Segoe UI", 24, "bold"),
    "body": ("Segoe UI", 12),
    "body_bold": ("Segoe UI", 12, "bold"),
    "caption": ("Segoe UI", 10),
    "code": ("Consolas", 11),
}


def apply_theme(mode: str = "Dark"):
    """Set global appearance mode: 'Dark', 'Light', or 'System'."""
    ctk.set_appearance_mode(mode)
    ctk.set_default_color_theme("blue")

