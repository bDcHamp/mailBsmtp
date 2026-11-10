"""
Windows System Tray Manager.
Minimizes the application to the notification area so the 24/7 engine runs silently.
"""

import threading
from PIL import Image, ImageDraw
import pystray


def create_default_tray_icon() -> Image.Image:
    """Generate a high-contrast 64x64 mail icon for the system tray."""
    img = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded blue background
    draw.rounded_rectangle([4, 4, 60, 60], radius=12, fill="#2563eb")

    # White envelope outline and flap
    draw.rectangle([14, 20, 50, 44], fill="#ffffff")
    draw.polygon([(14, 20), (32, 34), (50, 20)], fill="#93c5fd")
    draw.line([(14, 44), (28, 30)], fill="#bfdbfe", width=2)
    draw.line([(50, 44), (36, 30)], fill="#bfdbfe", width=2)

    return img


class SystemTrayManager:
    """Manages the background pystray tray icon and lifecycle."""

    def __init__(self, app):
        self.app = app
        self.tray_icon = None
        self._tray_thread = None

    def start(self):
        """Initialize and run system tray in a background thread."""
        if self.tray_icon is not None:
            return

        icon_image = create_default_tray_icon()
        menu = pystray.Menu(
            pystray.MenuItem("Open Marketing Mailer", self._on_open, default=True),
            pystray.MenuItem("Service Status", self._on_status, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit Completely", self._on_exit),
        )

        self.tray_icon = pystray.Icon(
            "MarketingMailer",
            icon_image,
            "Marketing SMTP Mailer (24/7 Service)",
            menu,
        )

        self._tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        self._tray_thread.start()

    def _on_open(self, icon=None, item=None):
        self.app.after(0, self.app.restore_from_tray)

    def _on_status(self, icon=None, item=None):
        pass

    def _on_exit(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.app.after(0, self.app.quit_app)

    def update_tooltip(self, text: str):
        if self.tray_icon:
            self.tray_icon.title = text

    def stop(self):
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None

