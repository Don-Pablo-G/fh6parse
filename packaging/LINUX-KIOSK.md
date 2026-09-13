# fh6parse Linux kiosk manual

Shop-floor install for **Raspberry Pi 3** with a **portrait 800×600** screen: boot, wait for a USB stick, pick an NC file with a rotary encoder, print an 80 mm ticket on a **MUNBYN P047**.

Python **3.10+** is required. Use **Raspberry Pi OS Bookworm** (32-bit Desktop is the practical image on a Pi 3).

---

## 1. What you need

| Item | Notes |
| --- | --- |
| Raspberry Pi 3 (B / B+) | 2.5 A PSU for the Pi. Do not power the printer from the Pi USB. |
| 800×600 LCD, mounted vertically | After rotation the framebuffer is **600×800**. That is what the app uses. |
| KY-040 rotary encoder | CLK and DT only. The shaft push-switch is unused. |
| Two momentary buttons | Normally-open, wired to GPIO and GND. |
| USB stick | FAT/exFAT/NTFS. Programs as `.nc` / `.NC` / `.tap` in the **stick root** only (not subfolders). |
| MUNBYN P047 (ITPP047) | USB, 80 mm ESC/POS, auto-cutter. Own mains PSU. |
| Keyboard | Only for first-time setup. Not needed on the shop floor. |

Default GPIO (**BCM** numbers, not header pin numbers):

| Function | BCM GPIO | Header pin |
| --- | --- | --- |
| Encoder CLK | 17 | 11 |
| Encoder DT | 27 | 13 |
| Full-report button | 22 | 15 |
| Minimal-report button | 23 | 16 |
| 3.3 V for encoder VCC | — | 1 or 17 |
| GND | — | 6, 9, or 14 |

Change pins in `/etc/fh6parse-kiosk.ini` if you wire them differently.

---

## 2. Hardware

### 2.1 Power and USB

- Pi on its own 5 V supply.
- P047 on its own supply; USB cable to the Pi is **data only** if the printer has a separate PSU.
- USB stick in any Pi USB port. Automount under `/media/pi/…` or `/run/media/…` is enough; the kiosk polls those paths.

### 2.2 GPIO rules

Pi GPIO is **3.3 V**. Do not feed 5 V into CLK, DT, or the button pins.

KY-040 **VCC → 3.3 V** (header pin 1), **GND → GND**. Many modules work at 3.3 V. If the module insists on 5 V, you still must not put 5 V on the Pi inputs (use a level shifter).

Buttons: one side to the GPIO, the other to GND. The app enables the internal pull-up, so the pin reads high until the button shorts it to ground.

Encoder **SW** (shaft click): leave unconnected.

### 2.3 Wiring diagram (defaults)

Pi 3 40-pin header, looking at the board with the USB ports down:

```
 3.3V  (1)  (2)  5V          ← encoder VCC to pin 1 only
 GPIO2 (3)  (4)  5V
 GPIO3 (5)  (6)  GND         ← shared GND (encoder GND + both buttons)
 GPIO4 (7)  (8)  GPIO14
  GND  (9)  (10) GPIO15
GPIO17 (11) (12) GPIO18      ← encoder CLK
GPIO27 (13) (14) GND         ← encoder DT
GPIO22 (15) (16) GPIO23      ← FULL button     MIN button
```

KY-040 typical labels:

| KY-040 | Pi |
| --- | --- |
| GND | pin 6 (GND) |
| + | pin 1 (3.3 V) |
| SW | not used |
| DT | pin 13 (GPIO 27) |
| CLK | pin 11 (GPIO 17) |

Each print button:

```
GPIO ── button ── GND
```

If turning the knob moves the highlight the wrong way, set `encoder_swap = true` in the ini (or swap CLK and DT).

### 2.4 Screen orientation

The panel is 800×600 landscape electronics, mounted as portrait. The OS must present **600×800**.

On Raspberry Pi OS, switch to **X11** first (tkinter + screensaver `xset` are unreliable on Wayland):

```
sudo raspi-config
```

- **Advanced Options → Wayland → X11**
- **System Options → Boot / Auto Login → Desktop autologin**
- Reboot

Then rotate. Either:

**Screen Configuration** (desktop): HDMI output → Orientation **right** or **left** until the picture matches the physical panel. Apply and “OK”.

Or in a terminal after login:

```
xrandr --output HDMI-1 --rotate right
```

(Use `xrandr` with no arguments to see the output name: `HDMI-1`, `HDMI-A-1`, ….)

To make rotation survive reboot, add the same `xrandr` line to `~/.config/autostart/` or `/etc/xdg/lxsession/LXDE-pi/autostart`.

Older firmware-only rotation (if you are still on `/boot/config.txt` and not KMS):

```
display_rotate=1
```

`1` and `3` are 90° / 270°. Pick the one that matches the mount.

### 2.5 Printer (MUNBYN P047)

USB to the Pi. The kiosk sends **raw ESC/POS** (48-column Font A, then cut). Do **not** print HTML or use a Windows GDI/POS-80 raster driver.

The app tries, in order:

1. `lp -d munbyn -o raw`
2. `lp -o raw` (CUPS default)
3. `/dev/usb/lp0`

---

## 3. Software

Do this on the Pi, as user `pi`, with network.

### 3.1 Packages

```
sudo apt update
sudo apt install -y git python3 python3-pip python3-tk \
    python3-gpiozero python3-rpi.gpio \
    cups cups-client cups-bsd \
    x11-xserver-utils
```

`python3-tk` is the kiosk UI. `python3-gpiozero` + `python3-rpi.gpio` read the encoder and buttons. `cups` is optional if you only write to `/dev/usb/lp0`. `x11-xserver-utils` provides `xset` so the panel can blank.

Confirm Python is 3.10 or newer:

```
python3 --version
```

### 3.2 Install fh6parse

**Option A — prebuilt one-file (this repo’s `dist/packages`)**

On a **32-bit** Raspberry Pi OS image use the `armv7` tarball. On **64-bit** Bookworm use `aarch64`.

```
cd /home/pi
tar -xzf fh6parse-*-raspberrypi-armv7.tar.gz
# or: tar -xzf fh6parse-*-raspberrypi-aarch64.tar.gz
chmod +x fh6parse
sudo cp fh6parse-kiosk.ini.example /etc/fh6parse-kiosk.ini
```

Run:

```
./fh6parse --kiosk --config /etc/fh6parse-kiosk.ini
```

For systemd, set `ExecStart=/home/pi/fh6parse --kiosk --config /etc/fh6parse-kiosk.ini` (path to the unpacked binary).

**Option B — from source**

```
cd /home/pi
git clone https://github.com/Don-Pablo-G/fh6parse.git
cd fh6parse
sudo pip3 install -e . --break-system-packages
```

`--break-system-packages` is normal on Bookworm when you are not using a venv. gpiozero stays the **apt** copy so it can see the Pi GPIO.

Check:

```
python3 -m fh6parse --version
```

Expect `fh6parse 1.2.0` or newer.

### 3.3 Kiosk config

```
sudo cp /home/pi/fh6parse/packaging/fh6parse-kiosk.ini.example /etc/fh6parse-kiosk.ini
sudo nano /etc/fh6parse-kiosk.ini
```

Leave the defaults unless your wiring or printer queue differs. Useful keys:

| Key | Default | Meaning |
| --- | --- | --- |
| `idle_seconds` | 60 | Black screen after this many seconds. `0` disables. |
| `encoder_clk` / `encoder_dt` | 17 / 27 | BCM pins |
| `button_full` / `button_min` | 22 / 23 | BCM pins |
| `encoder_swap` | false | Reverse knob direction |
| `printer_queue` | munbyn | CUPS queue name |
| `printer_device` | /dev/usb/lp0 | Fallback character device |
| `scan_depth` | 1 | USB root only. Raise to search subfolders. |
| `extensions` | `.nc,.tap` | File types (case-insensitive) |
| `extra_roots` | (empty) | Extra folders to list, comma-separated (for testing) |
| `fullscreen` | true | Shop display. Escape once exits fullscreen. |

### 3.4 Groups and devices

```
sudo usermod -aG gpio,lp,lpadmin pi
```

Log out and back in (or reboot) so the groups apply.

Check the printer node after plugging the P047 in:

```
lsusb
ls -l /dev/usb/lp0
```

If `/dev/usb/lp0` is missing, unplug/replug and look at `dmesg | tail`.

### 3.5 CUPS raw queue (recommended)

```
sudo lpadmin -p munbyn -E -v usb:/dev/usb/lp0 -m raw
sudo lpoptions -d munbyn
```

If `usb:/dev/usb/lp0` is rejected, list URIs and pick the P047:

```
sudo lpinfo -v
```

Then:

```
sudo lpadmin -p munbyn -E -v 'usb://...' -m raw
```

Test **raw** text, not a desktop print dialog:

```
printf 'TEST\n\n\n' | lp -d munbyn -o raw
```

You should get a short slip. The kiosk adds the cutter command itself.

### 3.6 First run (with keyboard)

On the graphical desktop:

```
python3 -m fh6parse --kiosk --config /etc/fh6parse-kiosk.ini
```

Without GPIO you can still move with **Up/Down**, print **F** (full) / **M** (min). Plug in a USB stick with `.nc` files; the list should fill by itself.

Desktop autostart of the kiosk is in the next section. Until then, Escape leaves fullscreen, Escape again closes the window.

---

## 4. Boot to kiosk

Copy the unit and enable it. The service assumes user `pi`, display `:0`, and Desktop autologin.

```
sudo cp /home/pi/fh6parse/packaging/fh6parse-kiosk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fh6parse-kiosk.service
```

Optional: turn off the *desktop* screensaver so it does not fight the app. In `/etc/xdg/lxsession/LXDE-pi/autostart` (path may vary) add:

```
@xset s off
@xset -dpms
```

The kiosk still blanks after 60 s via a black overlay and `xset dpms force off`.

Reboot. After the desktop appears, the CNC list should open fullscreen.

Logs:

```
journalctl -u fh6parse-kiosk -e
```

If the unit starts before X is ready, it will restart every 3 s until `:0` exists.

---

## 5. Daily use

1. Power on. Screen shows **Insert USB** (or the last stick if it was already plugged in).
2. Insert the USB stick. `.nc` / `.tap` files in the stick **root** appear.
3. Turn the encoder to highlight a file.
4. **FULL** — 80 mm ticket: operations, tool list, each tool change, warnings, min Z.
5. **MIN** — short ticket: per operation, only T, description, min Z, warnings.
6. After **60 seconds** with no encoder movement and no new USB, the screen goes black.
7. Wake: turn the encoder, or plug in a USB stick. The first encoder step only wakes; it does not skip a file.
8. Print buttons **do nothing** while the screen is asleep (avoids accidental tickets).

Parse happens at print time, not when the list is shown.

---

## 6. Troubleshooting

| Symptom | What to check |
| --- | --- |
| `GPIO off: …` on the status line | `python3-gpiozero` / `python3-rpi.gpio` installed; user in group `gpio`; pins not already claimed. |
| Knob does nothing | CLK/DT on 17/27; common GND; 3.3 V VCC. Try `encoder_swap = true`. |
| Knob skips or jitters | Shorter wires; module decoupling. gpiozero already debounces. |
| Buttons print on press and release | Use momentary NO to GND, not a latching switch. |
| List stays on Insert USB | Stick mounted? `ls /media/pi` / `ls /run/media`. Format FAT32. Files ending `.nc` or `.tap`. |
| `printer failed` | `ls -l /dev/usb/lp0`; user in `lp`; `lpstat -p munbyn`; test `lp -d munbyn -o raw`. Queue must be **raw**, not a raster POS-80 driver. |
| Garbage on the slip | CUPS is not raw, or a desktop “print HTML” path was used. The kiosk never sends HTML. |
| Ticket does not cut | Cutter empty/jammed. App already sends ESC/POS cut (`GS V`). |
| Screen never sleeps | `idle_seconds = 0`, or encoder bouncing. |
| Sleeps but never wakes on USB | Automount must create a **new** mount under `/media`, `/run/media`, or `/mnt`. Copying files onto an already-mounted stick does not wake (encoder does). |
| Black screen immediately | Desktop blanking plus app DPMS. Disable LXDE/Wayfire idle blank; keep kiosk `idle_seconds = 60`. |
| Wrong aspect / sideways UI | Rotate until `xdpyinfo` (or Screen Configuration) shows 600×800. App geometry is 600×800 fullscreen. |
| Service dead, UI never starts | `echo $DISPLAY` in a desktop terminal should be `:0`. `raspi-config` → X11, desktop autologin. `journalctl -u fh6parse-kiosk`. |
| Python 3.9 | Bullseye image. Install Bookworm, or build 3.10+. |

CLI without the kiosk (reports next to the NC file):

```
python3 -m fh6parse /path/program.nc
python3 -m fh6parse --format 80mm-min --stdout /path/program.nc
```

---

## 7. Files on disk

| Path | Role |
| --- | --- |
| `/home/pi/fh6parse` | Source checkout |
| `/etc/fh6parse-kiosk.ini` | Pins, printer, idle |
| `/etc/systemd/system/fh6parse-kiosk.service` | Autostart |
| `packaging/fh6parse-kiosk.ini.example` | Template |
| `packaging/fh6parse-kiosk.service` | Template |

Update:

```
cd /home/pi/fh6parse
git pull
sudo pip3 install -e . --break-system-packages
sudo systemctl restart fh6parse-kiosk
```
