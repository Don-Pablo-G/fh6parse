# fh6parse Linux kiosk manual

**Version 1.3.2.** Shop-floor install for **Raspberry Pi 3** with a **portrait 800×600** screen: boot, wait for a USB stick, pick an NC file with a rotary encoder, print an 80 mm ticket on a **MUNBYN P047**. Optional STEP isometrics on the slip. If the Pi is on the network, the kiosk can offer an on-screen **UPDATE**.

Python **3.10+** is required. Use **Raspberry Pi OS Bookworm** (32-bit Desktop is the practical image on a Pi 3).

1. [What you need](#1-what-you-need)
2. [Hardware](#2-hardware)
3. [Software](#3-software)
4. [Boot to kiosk](#4-boot-to-kiosk)
5. [Daily use](#5-daily-use)
6. [Troubleshooting](#6-troubleshooting)
7. [Files on disk](#7-files-on-disk)
8. [Updating (1.3.2)](#8-updating-the-kiosk)

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
| Company STEP folder (optional) | Network share of `.stp` / `.step` files. See **§3.7**. |
| Network (optional) | Only for git install and later **UPDATE**. Printing works offline. |
| Keyboard / mouse | First-time setup, SSH, or tap **UPDATE**. Not required for encoder + GPIO print. |

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

USB to the Pi. The kiosk sends **raw ESC/POS**: optional STEP bitmaps (`GS v 0`), then 48-column Font A, then cut. Do **not** print HTML or use a Windows GDI/POS-80 raster driver.

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

**Recommended — from source (git).** This is the shop update path.

```
cd /home/pi
git clone https://github.com/Don-Pablo-G/fh6parse.git
cd fh6parse
sudo pip3 install -e . --break-system-packages
```

For isometric views on the ticket, also install the CAD extra (**§3.7**). Skip it on a Pi 3 if `cascadio` has no wheel; tickets stay text-only.

```
sudo pip3 install -e '.[models]' --break-system-packages
```

`--break-system-packages` is normal on Bookworm when you are not using a venv. gpiozero stays the **apt** copy so it can see the Pi GPIO.

Allow user `pi` to restart the kiosk after an on-screen **UPDATE** (once, as root):

```
echo 'pi ALL=(root) NOPASSWD: /usr/bin/systemctl restart fh6parse-kiosk' | sudo tee /etc/sudoers.d/fh6parse-kiosk
sudo chmod 440 /etc/sudoers.d/fh6parse-kiosk
```

Check:

```
python3 -m fh6parse --version
```

Expect `fh6parse 1.3.2`. If the number is older, this clone is behind — `git fetch && git pull --ff-only` then check again (**§8**).

Later upgrades are **§8**. Do not run `pip install` on every pull. The kiosk does not update by itself.

**Air-gap first copy — prebuilt one-file** (this repo’s `dist/packages`). Not the upgrade path; use git for later updates.

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

The one-file ARM tarball does not bundle the CAD stack, so **§3.7** pictures are git-checkout only. There is no **UPDATE** button and `--update` refuses this install. To get the 1.3.2 shop update path later, switch to the git checkout above.

For systemd, set `ExecStart=/home/pi/fh6parse --kiosk --config /etc/fh6parse-kiosk.ini` (path to the unpacked binary).

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
| `model_roots` | (empty) | Company `.stp` / `.step` folders. Several paths, subfolders included. See **§3.7**. |
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

Without GPIO you can still use a **USB keyboard and mouse** at any time (hot-plug is fine). The kiosk keeps keyboard focus and the black screensaver wakes on a key, click, or mouse wheel.

| Input | While awake | While screensaver |
| --- | --- | --- |
| Arrows, mouse wheel, click a file | Move highlight | First event only wakes |
| **F** / **M** | Print full / min | Ignored (no ticket); another key or click wakes |
| GPIO FULL / MIN | Print | Ignored (no ticket, stays black) |
| Yellow **UPDATE** / **U** | Apply pending git update (button only if origin is ahead) | Wake first, then tap |
| **Esc** | Leave fullscreen, then close | Wake, then Esc again leaves fullscreen |

Plug in a USB stick with `.nc` files; the list should fill by itself.

Desktop autostart of the kiosk is in the next section. Until then, Escape leaves fullscreen, Escape again closes the window.

### 3.7 STEP models on the ticket

Optional. FULL and MIN tickets can show two opposite **solid** isometric views (visible surfaces, not wireframe), stacked at the top of the slip. The longest 3D axis is laid across the 80 mm width (~512 dots); height is cropped to the part, so a long thin shaft is a thin strip, not a metre of paper. A bulky part is capped (~30 mm of paper per view). Print never waits for a model.

**1. Point the kiosk at the CAD folders** in `/etc/fh6parse-kiosk.ini`. Several roots are allowed (comma or `:` / `;`). Subfolders are searched.

```
model_roots = /mnt/cad/stp,/mnt/cad/archive
```

Mount the company share before the kiosk starts. Install `cifs-utils` if needed, then:

```
sudo apt install -y cifs-utils
sudo mkdir -p /mnt/cad
sudo mount -t cifs //server/cad /mnt/cad -o guest,uid=pi,gid=pi,iocharset=utf8
```

Put a matching line in `/etc/fstab` so it survives reboot. If the share is down, the ticket is still text only.

**2. Install the CAD extra** (git checkout only; heavy: numpy, pillow, trimesh, cascadio):

```
sudo pip3 install -e '.[models]' --break-system-packages
```

If that install fails (no `cascadio` wheel on 32-bit Pi 3), leave it off. Matching still runs; nothing is rendered and the list icon stays off.

**3. Matching** starts at the first characters of the NC file name (and the `O` program title). The end of the STEP name may differ (`_Rev03`, `_OP1`, extra words). Nearby part numbers do not match (`D0134078` will not pick `D0134079`).

Revision is taken from the G-code header, then the title, then the file name:

| In the NC | What is used |
| --- | --- |
| `(REV 3)`, `(REV.03)`, `(REVISION A)` | that revision |
| `(Rewizja: 02)`, `(REW 2)`, `(WERSJA 1)` | that revision |
| `O01282 (SE0241282-0 WIERCENIA …)` | part `SE0241282`, rev `0` |
| `D0134078_Rev03.nc` / `D0134078-R2.nc` / `D0134078A.nc` | suffix on the name |
| No rev in header or name | latest matching `.stp` / `.step` |

If the program **has** a revision, only a STEP file with the **same** rev is used (not a newer one). If several files share that rev, the closest (shortest) name wins.

| NC | Header | Picked model |
| --- | --- | --- |
| `D0134078.nc` | `O04078 (D0134078)` (no REV) | `D0134078_Rev03.stp` over `_Rev02` |
| `D0134078.nc` | `(REV 2)` | `D0134078_Rev02.stp`, not Rev03 |
| `SE0241282.nc` | `O01282 (SE0241282-0 …)` | `SE0241282-0.stp` (or `_Rev0`) |
| `000814086.nc` | title `000814086 OP1/OP2` | `000814086_Rev02.stp` if that is latest |

**4. On the screen**, a **■** appears next to the file when the bitmap is rendered and ready. The walk and render run in the background for every USB file in the list. Cache: `/tmp/fh6parse-models`.

On **Windows**, the GUI has **STEP folders…**. Paths are saved as `model_roots` in `fh6parse-kiosk.ini` next to the exe. The Windows one-file build bundles the CAD stack; print still works if a model is missing.

---

## 4. Boot to kiosk

Copy the unit and enable it. The service assumes user `pi`, display `:0`, and Desktop autologin. If `model_roots` is on a NAS, mount that share in `fstab` so it is up before the kiosk starts. The sudoers line from **§3.2** must exist if you want the **UPDATE** button to restart the unit.

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
3. Turn the encoder to highlight a file. A **■** means the STEP views are ready for that program.
4. **FULL** — 80 mm ticket: stacked isometrics when ready, then operations, tool list, each tool change, warnings, min Z.
5. **MIN** — short ticket: stacked isometrics when ready, then per operation only T, description, min Z, warnings.
6. If there is no **■**, print anyway. The slip is text only.
7. After **60 seconds** with no encoder movement and no new USB, the screen goes black.
8. Wake: encoder, inserting a USB stick, or a **keyboard / mouse**. The first encoder step, key, or click only wakes; it does not skip a file or print. GPIO print buttons while asleep stay ignored.
9. Print buttons **do nothing** while the screen is asleep (avoids accidental tickets).
10. If the Pi is on the network and a newer git commit exists, a yellow **UPDATE** button appears **after this boot’s check**. Tap it (or **U**). Nothing is applied until then; print still works. After a successful update the kiosk restarts (needs the sudoers line in **§3.2** / **§8**).

Parse happens at print time, not when the list is shown. STEP matching and rendering run in the background and must not delay the ticket.

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
| Keyboard/mouse do nothing | Plug into the Pi USB; X11 picks them up. Click or press a key — the kiosk claims focus. **Esc** leaves fullscreen. GPIO print buttons still do not wake the screensaver. |
| Black screen immediately | Desktop blanking plus app DPMS. Disable LXDE/Wayfire idle blank; keep kiosk `idle_seconds = 60`. |
| Wrong aspect / sideways UI | Rotate until `xdpyinfo` (or Screen Configuration) shows 600×800. App geometry is 600×800 fullscreen. |
| Service dead, UI never starts | `echo $DISPLAY` in a desktop terminal should be `:0`. `raspi-config` → X11, desktop autologin. `journalctl -u fh6parse-kiosk`. |
| Python 3.9 | Bullseye image. Install Bookworm, or build 3.10+. |
| `--update` says one-file package | This Pi is running the ARM tarball. Copy a new tarball or reinstall from git (**§3.2**). |
| `--update` / fast-forward failed | Uncommitted edits or a diverged branch. See **§8.1**. Do not merge on the shop floor. |
| `--update` / **UPDATE** pulled but UI unchanged | `sudo systemctl restart fh6parse-kiosk`. Missing sudoers: **§3.2**. |
| **UPDATE** button never appears | Offline, one-file tarball, already up to date, or version older than 1.3.2 (**§8.1**). Check is only at kiosk start. `python3 -m fh6parse --version`. |
| **UPDATE** says failed / kiosk did not restart | `sudo -n systemctl restart fh6parse-kiosk` from user `pi` should succeed after **§3.2**. Then `sudo systemctl restart fh6parse-kiosk`. |
| No **■** next to files | `model_roots` empty or the share is not mounted (`ls` the path). CAD extra missing (`pip3 install -e '.[models]'`). Still rendering (wait). Rev in the G-code does not match any `.stp`. |
| **■** shows, ticket has no picture | CUPS queue is not **raw**. Printer rejected `GS v 0`. Test text-only first (`printf` in §3.5). |
| Pictures vanished after `--update` | `--update` runs `pip install -e .` **without** `[models]` when `pyproject.toml` changes. Re-run `sudo pip3 install -e '.[models]' --break-system-packages`. |
| Kiosk sluggish after USB insert | Huge CAD tree on a slow NAS. Narrow `model_roots` to the live folder, not the whole archive. Render is background and must not block print. |

CLI without the kiosk (reports next to the NC file):

```
python3 -m fh6parse /path/program.nc
python3 -m fh6parse --format 80mm-min --stdout /path/program.nc
```

---

## 7. Files on disk

| Path | Role |
| --- | --- |
| `/home/pi/fh6parse` | Source checkout (shop update path) |
| `/etc/fh6parse-kiosk.ini` | Pins, printer, idle, `model_roots` (never overwritten by **UPDATE**) |
| `/etc/systemd/system/fh6parse-kiosk.service` | Autostart |
| `/etc/sudoers.d/fh6parse-kiosk` | NOPASSWD restart for on-screen **UPDATE** |
| `packaging/fh6parse-kiosk.ini.example` | Template |
| `packaging/fh6parse-kiosk.service` | Template |
| `/tmp/fh6parse-models` | Cached STEP bitmaps (safe to delete) |

---

## 8. Updating the kiosk

This section is for **fh6parse 1.3.2** on a **git checkout** (`/home/pi/fh6parse`). Confirm first:

```
python3 -m fh6parse --version
```

You want `fh6parse 1.3.2`. The kiosk **never updates by itself**. Print works with or without a network.

### 8.1 First pull to 1.3.2 (already installed, older number)

If `--version` is older than 1.3.2, there is no on-screen **UPDATE** yet. SSH or plug in a keyboard:

```
cd /home/pi/fh6parse
git fetch
git pull --ff-only
python3 -m fh6parse --version
```

Add the sudoers line from **§3.2** if it is missing, then:

```
sudo systemctl restart fh6parse-kiosk
```

From this restart onward, later upgrades use **§8.2**.

If `git pull --ff-only` fails, the clone has local edits or a diverged branch. `git status`. Do not merge on the shop floor. Reset to `origin/master` only if you mean to discard local changes:

```
cd /home/pi/fh6parse
git fetch
git reset --hard origin/master
python3 -m fh6parse --version
sudo systemctl restart fh6parse-kiosk
```

### 8.2 On-screen UPDATE (1.3.2 and later)

On each kiosk start, a background thread runs `git fetch` (~20 s timeout) and compares `HEAD` to the tracked branch (`@{upstream}`, else `origin/HEAD`, else `origin/master`).

| After the check | What you see |
| --- | --- |
| Offline, timeout, one-file binary, or already current | No button. Print as usual. |
| Origin has a newer commit | Large yellow **UPDATE** at the bottom. Status: “Update available”. |

Tap **UPDATE** (touch or mouse) or press **U**. Print is paused only while that runs. Steps are the same as `--update` in **§8.3**. On success the unit restarts and the new version is live.

`pi` cannot restart a system unit unless you installed the sudoers file in **§3.2**. Without it, the pull may still succeed; restart by hand:

```
sudo systemctl restart fh6parse-kiosk
```

The check runs **once per start**. After you put a new commit on GitHub, reboot or restart the kiosk (or wait until the next power-on) before the button can appear.

### 8.3 Keyboard / SSH (`--update`)

Wake the screen if it is black. **Esc** once leaves fullscreen, **Esc** again closes the window if you need a desktop terminal. If systemd owns the display, open a terminal on `:0` or SSH as `pi`.

```
python3 -m fh6parse --version
python3 -m fh6parse --update
python3 -m fh6parse --version
```

`--update` and the on-screen button do this, in order:

1. `git pull --ff-only` in the clone (refuses messy merges)
2. `pip3 install -e .` **only if** `pyproject.toml` changed; otherwise skips pip. That command does **not** reinstall the `[models]` extra; see **§3.7** if pictures disappear.
3. `systemctl restart fh6parse-kiosk` if that unit exists; if that fails, `sudo -n systemctl restart fh6parse-kiosk`. Otherwise it prints “restart the kiosk yourself”

It never writes `/etc/fh6parse-kiosk.ini`. Pins, printer, idle, and `model_roots` stay as you set them.

### 8.4 One-file ARM tarball

No **UPDATE** button. `python3 -m fh6parse --update` (or `./fh6parse --update`) exits with a message to copy a new tarball or switch to a git clone. That package is a first copy, not the 1.3.2 upgrade path. To convert: follow **§3.2** (git + pip), point systemd `ExecStart` back to `python3 -m fh6parse --kiosk --config /etc/fh6parse-kiosk.ini`, then **§8.2**.

