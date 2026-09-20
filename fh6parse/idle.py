"""Kiosk screensaver gate: sleep after idle; GPIO print buttons do not wake."""

from __future__ import annotations


class ScreensaverGate:
    """GPIO print buttons do not wake the display.

    Wake: encoder, USB insert, optional spare GPIO, or a plugged-in
    keyboard / mouse (troubleshooting). Spare also blanks the panel.
    """

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

    def spare(self) -> str:
        """Optional sleep/wake GPIO. 'wake' if asleep, else 'sleep'.

        Works even when idle_seconds is 0 (no auto-blank). An unconnected
        pin never fires this.
        """
        if self.asleep:
            self.asleep = False
            return "wake"
        self.asleep = True
        return "sleep"

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

    def hid(self) -> str:
        """Keyboard or mouse: 'wake' if this event only turns the screen on."""
        if self.asleep:
            self.asleep = False
            return "wake"
        return "ok"

    def allow_print(self) -> bool:
        """False while asleep (GPIO / F / M / S ignored, screen stays black)."""
        return not self.asleep
