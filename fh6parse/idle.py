"""Kiosk screensaver gate: sleep after idle; wake on encoder or USB insert."""

from __future__ import annotations


class ScreensaverGate:
    """Print buttons do not wake the display. Encoder / USB insert do."""

    def __init__(self, idle_seconds: float = 60.0) -> None:
        self.idle_seconds = idle_seconds
        self.asleep = False

    @property
    def enabled(self) -> bool:
        return self.idle_seconds > 0

    def sleep(self) -> bool:
        """Enter screensaver. False if disabled or already asleep."""
        if not self.enabled or self.asleep:
            return False
        self.asleep = True
        return True

    def encoder(self) -> str:
        """'wake' if this rotation only turns the screen on, else 'step'."""
        if self.asleep:
            self.asleep = False
            return "wake"
        return "step"

    def usb_insert(self) -> str:
        """'wake' if the stick insertion turns the screen on, else 'ok'."""
        if self.asleep:
            self.asleep = False
            return "wake"
        return "ok"

    def allow_print(self) -> bool:
        """False while asleep (button is ignored, screen stays black)."""
        return not self.asleep
