"""
Unit tests for Desktop GUI components.
"""

import unittest
from PIL import Image

from gui.theme import COLORS, FONTS, apply_theme
from gui.tray import create_default_tray_icon


class TestDesktopGUI(unittest.TestCase):

    def test_theme_tokens(self):
        self.assertIn("dark", COLORS)
        self.assertIn("light", COLORS)
        self.assertEqual(COLORS["dark"]["accent"], "#3b82f6")
        self.assertIn("app_title", FONTS)

    def test_tray_icon_generation(self):
        icon_img = create_default_tray_icon()
        self.assertIsInstance(icon_img, Image.Image)
        self.assertEqual(icon_img.size, (64, 64))
        self.assertEqual(icon_img.mode, "RGBA")


if __name__ == "__main__":
    unittest.main()

