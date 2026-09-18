# fh6parse Linux kiosk manual

**Version 1.4.0.** Raspberry Pi 5 kiosk: portrait **800×600**, MUNBYN **P047**, USB `/dev/usb/lp0` print, isometric **line-art** STEP (stick `.stp` first), **D** vs T warnings, programmed cycle time and a per-tool share chart. Screen language is **Polish** by default (**F2** / **C** / the **PL**·**EN** chip for English). A **wireframe 3D cube** next to a file means the STEP views are ready. The screen shows **v1.4.0**. A yellow **UPDATE to …** button appears only when the network has a newer git commit — it does **not** apply until you tap it, then it restarts the kiosk. The Windows office exe uses the same button against a GitHub Release.

Python **3.10+** is required (Bookworm ships 3.11). Use **Raspberry Pi OS 64-bit Desktop** (Bookworm or later). Pi 5 has no 32-bit OS.

The 40-pin header uses the **same BCM numbers as Pi 3/4**. GPIO on Pi 5 goes through the **RP1** chip: `RPi.GPIO` does **not** work. The kiosk uses gpiozero with **lgpio**. Still switch the desktop to **X11** (tkinter + `xset` blanking).

1. [What you need](#1-what-you-need)
2. [Hardware](#2-hardware)
3. [Software](#3-software)
4. [Boot to kiosk](#4-boot-to-kiosk)
5. [Daily use](#5-daily-use)
6. [Troubleshooting](#6-troubleshooting)
7. [Files on disk](#7-files-on-disk)
8. [Updating (1.4.0)](#8-updating-the-kiosk)
9. [Field test](#9-field-test)

---

## 1. What you need

| Item | Notes |
| --- | --- |
| Raspberry Pi 5 | Official **27 W USB-C** PSU (5 V / 5 A). Do not use a Pi 3 2.5 A supply. Do not power the printer from the Pi USB. Active cooler recommended in a closed enclosure. |
| micro-HDMI cable | Pi 5 has two **micro-HDMI** ports. Use **HDMI0** (the port next to USB-C power) for the kiosk panel. |
| 800×600 LCD, mounted vertically | After rotation the framebuffer is **600×800**. That is what the app uses. |
| KY-040 rotary encoder | CLK and DT only. The shaft push-switch is unused. |
| Two momentary buttons | Normally-open, wired to GPIO and GND. |
| USB stick | FAT/exFAT/NTFS. Programs as `.nc` / `.NC` / `.tap` in the **stick root** only (not subfolders). |
| MUNBYN P047 (ITPP047) | USB, 80 mm ESC/POS, auto-cutter. Own mains PSU. |
| Company STEP folder (optional) | NAS of `.stp` / `.step` if the stick has none. See **§3.7**. Stick copy is enough. |
| Network (optional) | Only for git install and later **UPDATE**. Printing works offline. |
| Keyboard / mouse | First-time setup, **settings** (language, GPIO pins, encoder ticks), SSH, or tap **UPDATE**. Not required for encoder + GPIO print. |

Default GPIO (**BCM** numbers, not header pin numbers):

| Function | BCM GPIO | Header pin |
| --- | --- | --- |
| Encoder CLK | 17 | 11 |
| Encoder DT | 27 | 13 |
| Full-report button | 22 | 15 |
| Minimal-report button | 23 | 16 |
| 3.3 V for encoder VCC | — | 1 or 17 |
| GND | — | 6, 9, or 14 |

Change pins in **settings** (**F2** / **C** / **PL**·**EN**) or in `/etc/fh6parse-kiosk.ini`. Settings write `~/.config/fh6parse/ui.ini` (and the main ini if it is writable).

---

## 2. Hardware

### 2.1 Power and USB

- Pi 5 on the official USB-C 5 V / 5 A supply. USB-C on the Pi is **power only**.
- P047 on its own supply; USB cable to a Pi **USB-A** port is **data only** if the printer has a separate PSU.
- USB stick in any USB-A port (USB 2 or USB 3). Automount under `/media/<user>/…` or `/run/media/…` is enough; the kiosk polls those paths.

### 2.2 GPIO rules

Pi GPIO is **3.3 V** (unchanged on Pi 5). Do not feed 5 V into CLK, DT, or the button pins.

KY-040 **VCC → 3.3 V** (header pin 1), **GND → GND**. Many modules work at 3.3 V. If the module insists on 5 V, you still must not put 5 V on the Pi inputs (use a level shifter).

Buttons: one side to the GPIO, the other to GND. The app enables the internal pull-up, so the pin reads high until the button shorts it to ground.

Encoder **SW** (shaft click): leave unconnected.

### 2.3 Wiring diagram (defaults)

Pi 5 40-pin header (same BCM layout as Pi 3/4), looking at the board with the USB-A / Ethernet ports down:

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

If turning the knob moves the highlight the wrong way, use **Reverse** in settings (or `encoder_swap = true`, or swap CLK and DT). **Ticks per tooth** is GPIO ticks from one rest valley to the next. The list changes halfway (a 36-tooth knob is 10° per file, ~5° to change the highlight), so a small wiggle at rest does not skip files.

### 2.4 Screen orientation

The panel is 800×600 landscape electronics, mounted as portrait. The OS must present **600×800**.

On Raspberry Pi OS the default is **Wayland**. Switch to **X11** (tkinter + screensaver `xset` are unreliable on Wayland/labwc):

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
xrandr --output HDMI-A-1 --rotate right
```

(Use `xrandr` with no arguments to see the output name: `HDMI-A-1`, `HDMI-1`, … . Pi 5 KMS is usually `HDMI-A-1` for HDMI0.)

To make rotation survive reboot, add the same `xrandr` line to `~/.config/autostart/` or `/etc/xdg/lxsession/LXDE-pi/autostart`.

Do not use legacy `display_rotate=` in `/boot/firmware/config.txt`. Pi 5 is KMS-only.

### 2.5 Printer (MUNBYN P047)

USB to the Pi. The kiosk sends **raw ESC/POS**: optional STEP bitmaps (`GS v 0`), then 48-column Font A, then cut. Do **not** print HTML or use a Windows GDI/POS-80 raster driver.

The app writes that blob to **`/dev/usb/lp0`** first (same as `open("/dev/usb/lp0", "wb").write(...)`). CUPS is not involved on a working Pi. Named CUPS (`lp -d munbyn -o raw`) is only a fallback if the USB node is missing or busy. There is no `lp` default-queue attempt.

If CUPS has already claimed the printer, the USB write fails with *Device or resource busy*. Stop or disable that queue (or CUPS) so `usblp` owns `/dev/usb/lp0`.

---

## 3. Software

Do this on the Pi, as user **`kiosk`**, with network.

### 3.1 Packages

```
sudo apt update
sudo apt install -y git python3 python3-pip python3-tk \
    python3-gpiozero python3-lgpio python3-rpi-lgpio \
    x11-xserver-utils
```

Do **not** install `python3-rpi.gpio` on a Pi 5. That library talks to the old SoC GPIO; Pi 5 GPIO is on RP1. `python3-lgpio` is the driver; `python3-rpi-lgpio` is only a compatibility shim. The kiosk prefers lgpio automatically.

`python3-tk` is the kiosk UI. **Do not install CUPS** for the shop P047 — the kiosk prints by writing `/dev/usb/lp0`. `x11-xserver-utils` provides `xset` so the panel can blank.

Confirm Python is 3.10 or newer:

```
python3 --version
```

### 3.2 Install fh6parse

**Recommended — from source (git).** This is the shop update path.

```
cd /home/kiosk
git clone https://github.com/Don-Pablo-G/fh6parse.git
cd fh6parse
sudo pip3 install -e . --break-system-packages
```

For isometric views on the ticket, also install the CAD extra (**§3.7**). On 64-bit Pi 5 this usually has wheels. If `cascadio` fails, skip it; tickets stay text-only.

```
sudo pip3 install -e '.[models]' --break-system-packages
```

`--break-system-packages` is normal on Bookworm when you are not using a venv. gpiozero stays the **apt** copy so it can see the Pi GPIO.

Allow user `kiosk` to restart the kiosk after an on-screen **UPDATE** (once, as root):

```
echo 'kiosk ALL=(root) NOPASSWD: /usr/bin/systemctl restart fh6parse-kiosk' | sudo tee /etc/sudoers.d/fh6parse-kiosk
sudo chmod 440 /etc/sudoers.d/fh6parse-kiosk
```

Check:

```
python3 -m fh6parse --version
```

Expect `fh6parse 1.4.0`. If the number is older, this clone is behind — `git fetch && git pull --ff-only` then check again (**§8**).

Later upgrades are **§8**. Do not run `pip install` on every pull. The kiosk does not update by itself.

**Air-gap first copy — prebuilt one-file** (this repo’s `dist/packages`). Not the upgrade path; use git for later updates.

On a Pi 5 use the **aarch64** tarball only (there is no 32-bit Raspberry Pi OS for Pi 5).

```
cd /home/kiosk
tar -xzf fh6parse-*-raspberrypi-aarch64.tar.gz
chmod +x fh6parse
sudo cp fh6parse-kiosk.ini.example /etc/fh6parse-kiosk.ini
```

Run:

```
./fh6parse --kiosk --config /etc/fh6parse-kiosk.ini
```

The one-file ARM tarball does not bundle the CAD stack, so **§3.7** pictures are git-checkout only. There is no **UPDATE** button and `--update` refuses this install. To get the 1.4.0 shop update path later, switch to the git checkout above.

For systemd, set `ExecStart=/home/kiosk/fh6parse --kiosk --config /etc/fh6parse-kiosk.ini` (path to the unpacked binary).

### 3.3 Kiosk config

```
sudo cp /home/kiosk/fh6parse/packaging/fh6parse-kiosk.ini.example /etc/fh6parse-kiosk.ini
sudo nano /etc/fh6parse-kiosk.ini
```

Leave the defaults unless your wiring or printer queue differs. Useful keys:

| Key | Default | Meaning |
| --- | --- | --- |
| `idle_seconds` | 60 | Black screen after this many seconds. `0` disables. |
| `encoder_clk` / `encoder_dt` | 17 / 27 | BCM pins. Change in **settings** or here. |
| `button_full` / `button_min` | 22 / 23 | BCM pins for FULL / MIN. Change in **settings** or here. |
| `encoder_swap` | false | Reverse knob direction |
| `encoder_steps` | 1 | GPIO ticks from one tooth valley to the next. Highlight changes at half a tooth so rest is stable. |
| `printer_device` | /dev/usb/lp0 | USB printer node (**tried first**) |
| `printer_queue` | (empty) | Optional CUPS name; used only if the USB node fails. Empty = never call `lp`. |
| `scan_depth` | 1 | USB root only. Raise to search subfolders. |
| `extensions` | `.nc,.tap` | File types (case-insensitive) |
| `extra_roots` | (empty) | Extra folders to list, comma-separated (for testing) |
| `model_roots` | (empty) | Optional company `.stp` folders. USB stick is searched first. See **§3.7**. |
| `language` | `pl` | Screen language: `pl` (default) or `en`. Change on the kiosk in **settings** (**F2** / **C**, or click **PL** / **EN**). GPIO pins, mill, and encoder ticks are on the same panel. Stored in `~/.config/fh6parse/ui.ini` (and in this ini if it is writable). |
| `machine` | `default` | Id of the mill used for cycle time (`[machine.<id>]` below). Change in **settings**. |
| `fullscreen` | true | Shop display. Escape once exits fullscreen. |

Add one `[machine.<id>]` section per mill. Built-in **Default mill** is 20 m/min rapids and 0 s tool change until you pick another. Keys:

| Key | Default | Meaning |
| --- | --- | --- |
| `name` | the id | Label on the kiosk, Windows GUI, and tickets |
| `rapid_mm_min` | 20000 | Linear G0 rate (mm/min) for XYZ time |
| `rotary_deg_min` | 5400 | B/C G0 rate (deg/min) |
| `tool_change_s` | 0 | Seconds added at every Txx M6 |

Example:

```
machine = vf-4ss

[machine.vf-4ss]
name = Haas VF-4SS
rapid_mm_min = 25400
rotary_deg_min = 5400
tool_change_s = 2.8
```

### 3.4 Groups and devices

```
sudo usermod -aG gpio,lp kiosk
```

Log out and back in (or reboot) so the groups apply. Printer node check is **§3.5**.

### 3.5 Direct USB printer (recommended)

No CUPS. After the P047 is plugged in:

```
lsusb
ls -l /dev/usb/lp0
```

User `kiosk` must be able to write the node (`lp` group, then log out / reboot). Test the same write the kiosk uses:

```
python3 - <<'PY'
from pathlib import Path
Path("/dev/usb/lp0").write_bytes(b"\x1b@TEST\n\n\n\x1dVB\x00")
PY
```

You should get a short slip and a cut. If you see *Permission denied*, the group has not applied yet. If you see *Device or resource busy*, something else (usually CUPS) has the printer — `sudo systemctl stop cups` and try again, then disable CUPS so it does not come back:

```
sudo systemctl disable --now cups
```

If `/dev/usb/lp0` is missing, unplug/replug and look at `dmesg | tail`. A second printer can appear as `/dev/usb/lp1` — set `printer_device` in the ini.

**CUPS is not required.** Leave `printer_queue` empty to never call `lp`. Only set a raw queue if the USB node never appears on that machine.

### 3.6 First run (with keyboard)

On the graphical desktop:

```
python3 -m fh6parse --kiosk --config /etc/fh6parse-kiosk.ini
```

Without GPIO you can still use a **USB keyboard and mouse** at any time (hot-plug is fine). The kiosk keeps keyboard focus and the black screensaver wakes on a key, click, or mouse wheel.

The shop screen is **Polish** unless `language = en` is set. Open **settings** with the keyboard or mouse (not the encoder): **F2** or **C**, or click the **PL** / **EN** chip next to the version. Pick **Polski** or **English**, the mill (rapids and tool-change time from `[machine.<id>]` in this ini), BCM pin numbers for CLK / DT / FULL / MIN, knob reverse, and **ticks per tooth** (GPIO ticks from one rest valley to the next; the highlight changes halfway so a wiggle at rest does not skip files). Language, mill, and GPIO are written to `~/.config/fh6parse/ui.ini` (user `kiosk` can write this even when `/etc/fh6parse-kiosk.ini` is root-owned) and, if permitted, into the main ini. Pin changes take effect immediately (GPIO is reopened). **Esc** closes settings first; the next **Esc** still leaves fullscreen. Encoder or a GPIO print button closes settings without printing / skipping a file.

| Input | While awake | While screensaver |
| --- | --- | --- |
| Arrows, mouse wheel, click a file | Move highlight | First event only wakes |
| **F** / **M** | Print full / min | Ignored (no ticket); another key or click wakes |
| GPIO FULL / MIN | Print | Ignored (no ticket, stays black) |
| Yellow **UPDATE to …** / **U** | One tap: pull, then restart kiosk | Wake first, then tap |
| **F2** / **C** / click **PL**·**EN** | Open or close settings (language, pins, encoder ticks) | Wake first |
| In settings: arrows / wheel / **Polski**·**English** | Switch language | — |
| In settings: **+** / **−** | BCM pins and ticks per tooth | — |
| **Esc** | Close settings, else leave fullscreen, then close | Wake, then Esc again leaves fullscreen |

Plug in a USB stick with `.nc` files; the list should fill by itself.

Desktop autostart of the kiosk is in the next section. Until then, Escape leaves fullscreen, Escape again closes the window.

### 3.7 STEP models on the ticket

Optional. The kiosk looks for a matching `.stp` / `.step` **on the USB stick first** (same folder as the `.nc`, then subfolders on that stick). No NAS is required. Company folders in `model_roots` are a fallback if the stick has no match.

FULL and MIN tickets can show two opposite **true isometric** views (45° then ~35.3° — look along the cube diagonal), as **visible edges only** (silhouette + sharp creases, no shading). Through-holes draw as ellipses (near rim, and the far rim only where you can see through). The longest 3D axis is laid across the 80 mm width (~512 dots); height is cropped to the part, so a long thin shaft is a thin strip, not a metre of paper. A bulky part is capped (~30 mm of paper per view). Print never waits for a model. After an update, delete `/tmp/fh6parse-models` so old shaded bitmaps are not reused.

**1. USB (usual shop path).** Put the STEP file next to the program, or in a subfolder on the same stick:

```
D0134078.nc
D0134078_Rev03.stp
```

or `D0134078.nc` plus `cad/D0134078_Rev03.stp`. The kiosk indexes the stick when it is inserted. Matching rules are **§3.7 step 4**. CAD extra (**step 3**) is still required to draw the picture.

**2. Optional company CAD folders** in `/etc/fh6parse-kiosk.ini` if the stick has no STEP. Several roots are allowed (comma or `:` / `;`). Subfolders are searched. A file on the stick always wins over the NAS.

```
model_roots = /mnt/cad/stp,/mnt/cad/archive
```

Mount the company share before the kiosk starts. Install `cifs-utils` if needed, then:

```
sudo apt install -y cifs-utils
sudo mkdir -p /mnt/cad
sudo mount -t cifs //server/cad /mnt/cad -o guest,uid=kiosk,gid=kiosk,iocharset=utf8
```

Put a matching line in `/etc/fstab` so it survives reboot. If the share is down, the ticket is still text only.

**3. Install the CAD extra** (git checkout only; heavy: numpy, pillow, trimesh, cascadio):

```
sudo pip3 install -e '.[models]' --break-system-packages
```

If that install fails, leave it off. Matching still runs; nothing is rendered and the list icon stays off.

**4. Matching** starts at the first characters of the NC file name (and the `O` program title). The end of the STEP name may differ (`_Rev03`, `_OP1`, extra words). Nearby part numbers do not match (`D0134078` will not pick `D0134079`).

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

**5. On the screen**, a small **wireframe 3D cube** appears next to the file when the bitmap is rendered and ready (same icon as the legend under the title — the same visible-edge isometric language as the ticket). The walk and render run in the background for every USB file in the list. Cache: `/tmp/fh6parse-models`.

On **Windows**, the GUI also searches next to the opened NC file. **STEP folders…** is the NAS fallback. Paths are saved as `model_roots` in `fh6parse-kiosk.ini` next to the exe. The Windows one-file build bundles the CAD stack; print still works if a model is missing.

---

## 4. Boot to kiosk

Copy the unit and enable it. The service assumes user `kiosk`, display `:0`, and Desktop autologin. If `model_roots` is on a NAS, mount that share in `fstab` so it is up before the kiosk starts. The sudoers line from **§3.2** must exist if you want the **UPDATE** button to restart the unit.

```
sudo cp /home/kiosk/fh6parse/packaging/fh6parse-kiosk.service /etc/systemd/system/
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

1. Power on. Screen shows **Włóż pendrive** / **Insert USB** (or the last stick if it was already plugged in). The kiosk is Polish unless settings were changed.
2. Insert the USB stick. `.nc` / `.tap` files in the stick **root** appear.
3. Turn the encoder to highlight a file. A **3D cube** next to the name means the STEP views are ready for that program.
4. **FULL** — 80 mm ticket: stacked line-art isometrics when ready, then operations, cycle time, a share chart of each T, tool list, each tool change (time and % of cycle), warnings, min Z.
5. **MIN** — short ticket: stacked line-art isometrics when ready, then per operation cycle time, share chart of each T, then T, H/D/S to load, description, min Z, and H/D/G95 mismatch flags.
6. If there is no cube, print anyway. The slip is text only.
7. Status after a good print: **`device:/dev/usb/lp0`**. If it says `lp:…`, CUPS took the job — **§3.5**.
8. **WARNING:** lines: `H{n} does not match T{tool}` on G43, `D{n} does not match T{tool}` on any D, and `G95 still active…` if feed-per-rev was not cancelled with G94 before the next tool (or M30). Matching H/D stay quiet. Comments with `!` print as **Programmer notes**.
9. After **60 seconds** with no encoder movement and no new USB, the screen goes black.
10. Wake: encoder, inserting a USB stick, or a **keyboard / mouse**. The first encoder step, key, or click only wakes; it does not skip a file or print. GPIO print buttons while asleep stay ignored.
11. Settings: **F2** / **C** or the **PL**/**EN** chip (mouse) — **§3.6**. Encoder does not open settings. Pins and ticks per tooth are on that panel.
12. Print buttons **do nothing** while the screen is asleep (avoids accidental tickets).
13. Current version is **v…** at the top right. If the Pi is on the network and origin is ahead, a yellow **UPDATE to x.y.z** button appears **after this boot’s check**. It does **not** update by itself. One tap installs and **restarts** the kiosk (sudoers in **§3.2**). Print still works until you tap it.

Parse happens at print time, not when the list is shown. STEP matching and rendering run in the background and must not delay the ticket.

---

## 6. Troubleshooting

| Symptom | What to check |
| --- | --- |
| `GPIO off: …` on the status line | `python3-gpiozero` and `python3-lgpio` installed (not `python3-rpi.gpio` on Pi 5); user in group `gpio`; pins not already claimed. |
| Knob does nothing | CLK/DT on the BCM numbers shown in settings (defaults 17/27); common GND; 3.3 V VCC. Try **Reverse**. |
| Knob skips or jitters at rest | Raise **Ticks per tooth** so the valley is several GPIO ticks wide; highlight only changes halfway to the next tooth. Shorter wires; module decoupling. The kiosk also sets a short encoder `bounce_time` for Pi 5. |
| Buttons print on press and release | Use momentary NO to GND, not a latching switch. |
| List stays on Insert USB / Włóż pendrive | Stick mounted? `ls /media` / `ls /run/media`. Format FAT32. Files ending `.nc` or `.tap`. |
| `printer failed` | `ls -l /dev/usb/lp0`; user `kiosk` in group `lp`; test the Python write in **§3.5**. *Permission denied* → log out after `usermod`. *Busy* → CUPS still owns the printer (`sudo systemctl disable --now cups`). |
| Garbage on the slip | CUPS grabbed the job. The kiosk writes `/dev/usb/lp0` first; disable CUPS (**§3.5**). Status must show `device:/dev/usb/lp0`, not `lp:…`. |
| Ticket does not cut | Cutter empty/jammed. App already sends ESC/POS cut (`GS V`). |
| Screen never sleeps | `idle_seconds = 0`, or encoder bouncing. Still on Wayland? Switch to X11 so `xset` works. |
| Keyboard/mouse do nothing | Plug into the Pi USB-A; X11 picks them up. Click or press a key — the kiosk claims focus. **F2** / **C** opens settings. **Esc** closes settings, then leaves fullscreen. GPIO print buttons still do not wake the screensaver. |
| Language resets to Polish after you picked English | Stored in `/home/kiosk/.config/fh6parse/ui.ini`. Pick **English** again in settings. **UPDATE** does not delete that file. Pins and ticks live in the same overlay. |
| Screen stays in English and **F2** does nothing | Wake first if the screen is black. Click the **EN** chip next to **v…**. Encoder never opens settings. |
| Black screen immediately | Desktop blanking plus app DPMS. Disable LXDE idle blank; keep kiosk `idle_seconds = 60`. |
| Wrong aspect / sideways UI | Rotate until `xdpyinfo` (or Screen Configuration) shows 600×800. App geometry is 600×800 fullscreen. Pi 5 output is often `HDMI-A-1`. |
| Service dead, UI never starts | `echo $DISPLAY` in a desktop terminal should be `:0`. `raspi-config` → X11, desktop autologin. `journalctl -u fh6parse-kiosk`. Unit `User=` must be `kiosk`. |
| Undervoltage / random reboots | Official 27 W PSU. A phone charger or Pi 3 supply is not enough. |
| Python 3.9 | Wrong image. Flash 64-bit Raspberry Pi OS Desktop for Pi 5. |
| `--update` says one-file package | This Pi is running the ARM tarball. Copy a new tarball or reinstall from git (**§3.2**). |
| `--update` / fast-forward failed | Uncommitted edits or a diverged branch. See **§8.1**. Do not merge on the shop floor. |
| `--update` / **UPDATE** pulled but UI unchanged | `sudo systemctl restart fh6parse-kiosk`. Missing sudoers: **§3.2**. |
| **UPDATE** button never appears | Offline, one-file tarball, already up to date. Check is only at kiosk start. Screen should show **v1.4.0**. |
| **UPDATE** says failed / kiosk did not restart | `sudo -n systemctl restart fh6parse-kiosk` from user `kiosk` should succeed after **§3.2**. Then `sudo systemctl restart fh6parse-kiosk`. |
| No **3D cube** next to files | No matching `.stp` on the stick (or in `model_roots`). CAD extra missing (`pip3 install -e '.[models]'`). Still rendering (wait). G-code rev does not match any `.stp`. |
| Cube shows, ticket has no picture | Status not `device:/dev/usb/lp0` (CUPS intercepted). Printer rejected `GS v 0`. Test text-only first (**§3.5**). |
| Pictures vanished after `--update` | `--update` runs `pip install -e .` **without** `[models]` when `pyproject.toml` changes. Re-run `sudo pip3 install -e '.[models]' --break-system-packages`. |
| Pictures still shaded / grey mush | Old cache. `rm -rf /tmp/fh6parse-models` and wait for the cube again. The current renderer is black edges on white only. |
| No `WARNING:` for a wrong D | Clone is older than this pull. `git log -1 --oneline` must mention D vs T. D is checked on G43 and on G41/G42. |
| No `WARNING:` after tapping / G95 | Next `Txx M6` (or M30) must still be in G95. A `G94` on the next tool’s line cancels it. |

CLI without the kiosk (reports next to the NC file):

```
python3 -m fh6parse /path/program.nc
python3 -m fh6parse --format 80mm-min --stdout /path/program.nc
```

---

## 7. Files on disk

| Path | Role |
| --- | --- |
| `/home/kiosk/fh6parse` | Source checkout (shop update path) |
| `/etc/fh6parse-kiosk.ini` | Pins, printer, idle, `model_roots` (never overwritten by **UPDATE**) |
| `/home/kiosk/.config/fh6parse/ui.ini` | Screen language, GPIO pins, encoder ticks. Written by settings. Survives **UPDATE**. |
| `/etc/systemd/system/fh6parse-kiosk.service` | Autostart |
| `/etc/sudoers.d/fh6parse-kiosk` | NOPASSWD restart for on-screen **UPDATE** |
| `packaging/fh6parse-kiosk.ini.example` | Template |
| `packaging/fh6parse-kiosk.service` | Template |
| `/tmp/fh6parse-models` | Cached STEP bitmaps (safe to delete) |

---

## 8. Updating the kiosk

This section is for **fh6parse 1.4.0** on a **git checkout** (`/home/kiosk/fh6parse`). Confirm first:

```
python3 -m fh6parse --version
```

You want `fh6parse 1.4.0` (also **v1.4.0** on the kiosk). The kiosk **never updates by itself**. Print works with or without a network.

### 8.1 First pull to 1.4.0 (already installed, older number)

If `--version` is older than 1.4.0, SSH as `kiosk`:

```
cd /home/kiosk/fh6parse
git fetch
git pull --ff-only
python3 -m fh6parse --version
```

Add the sudoers line from **§3.2** if it is missing, then:

```
sudo systemctl restart fh6parse-kiosk
```

From this restart onward, later upgrades use **§8.2**.

If `git pull --ff-only` fails, the clone has local edits or a diverged branch. `git status`. Do not merge on the shop floor.

### 8.2 On-screen UPDATE (1.3.2 and later)

On each kiosk start, a background thread runs `git fetch` (~20 s timeout) and compares `HEAD` to the tracked branch (`@{upstream}`, else `origin/HEAD`, else `origin/master` / `origin/main`). **Nothing is installed until you tap the button.**

| After the check | What you see |
| --- | --- |
| Offline, timeout, one-file binary, or already current | No button. **v…** stays at the top. Print as usual. |
| Origin has a newer commit | Yellow **UPDATE to x.y.z** (or a short git hash if the number did not change). Status: `v1.4.0 → x.y.z · tap UPDATE to install and restart`. |

Tap **UPDATE** once (touch or **U**). That is the only action: `git pull --ff-only`, pip only if `pyproject.toml` changed, then **restart** `fh6parse-kiosk`. Print is paused only while that runs. The new version is live after the restart.

`kiosk` cannot restart a system unit unless you installed the sudoers file in **§3.2**. Without it the pull may succeed and the screen stays on the old process — then:

```
sudo systemctl restart fh6parse-kiosk
```

The check runs **once per start**. After you put a new commit on GitHub, reboot or restart the kiosk (or wait until the next power-on) before the button can appear.

### 8.3 Keyboard / SSH (`--update`)

Wake the screen if it is black. **Esc** once leaves fullscreen, **Esc** again closes the window if you need a desktop terminal. If systemd owns the display, open a terminal on `:0` or SSH as `kiosk`.

```
python3 -m fh6parse --version
python3 -m fh6parse --update
python3 -m fh6parse --version
```

`--update` and the on-screen button do this, in order:

1. `git pull --ff-only` in the clone (refuses messy merges)
2. `pip3 install -e .` **only if** `pyproject.toml` changed; otherwise skips pip. That command does **not** reinstall the `[models]` extra; see **§3.7** if pictures disappear.
3. `systemctl restart fh6parse-kiosk` if that unit exists; if that fails, `sudo -n systemctl restart fh6parse-kiosk`. Otherwise it prints “restart the kiosk yourself”

It never writes `/etc/fh6parse-kiosk.ini` or `~/.config/fh6parse/ui.ini`. Pins, printer, idle, `model_roots`, and language stay as you set them.

### 8.4 One-file ARM tarball

No **UPDATE** button. `python3 -m fh6parse --update` (or `./fh6parse --update`) exits with a message to copy a new tarball or switch to a git clone. That package is a first copy, not the 1.4.0 upgrade path. To convert: follow **§3.2** (git + pip), point systemd `ExecStart` back to `python3 -m fh6parse --kiosk --config /etc/fh6parse-kiosk.ini`, then **§8.2**.

---

## 9. Field test

Take this sheet to the Pi. The kiosk must show **v1.4.0** at the top right.

**1. Get this code onto the Pi** (user `kiosk`):

```
cd /home/kiosk/fh6parse
git fetch
git checkout main
git pull --ff-only
git log -1 --oneline
sudo systemctl restart fh6parse-kiosk
```

`git log -1` should mention **1.4.0** (cycle time / share chart, Windows UPDATE). STEP isometrics, D vs T, and USB `/dev/usb/lp0` are already in older commits. Or wait for the yellow **UPDATE** after a restart (check runs once per boot).

Clear old STEP bitmaps:

```
rm -rf /tmp/fh6parse-models
```

If `/etc/fh6parse-kiosk.ini` still has `printer_queue = munbyn`, you can leave it (USB is tried first) or comment it out. User `kiosk` must be in group `lp`. If the printer is busy:

```
sudo systemctl disable --now cups
```

**2. Printer (P047)**

| Check | Pass |
| --- | --- |
| `ls -l /dev/usb/lp0` exists, writable by `kiosk` | |
| Python test in **§3.5** prints TEST and cuts | |
| FULL ticket status: `device:/dev/usb/lp0` (not `lp:…`) | |
| Ticket text is readable (PC852 Polish comments), then cut | |
| No CUPS garbage / doubled jobs | |

**3. D and H vs tool number**

Use a program with a wrong offset, or a known sample (`000814086.nc` T10 with H25 D25).

| Check | Pass |
| --- | --- |
| Wrong H on G43 → `WARNING: H… does not match T…` | |
| Wrong D on G43 → `WARNING: D… does not match T…` | |
| Wrong D on G41/G42 → same D warning, once | |
| Matching D (= T) → no D warning | |
| G95 then next T without G94 → `WARNING: G95 still active…` | |
| `(…!…)` comments listed as programmer notes | |

**4. STEP views** (`.stp` on the USB stick, or `model_roots`; CAD extra required)

| Check | Pass |
| --- | --- |
| Stick has `Program.nc` + matching `.stp` (root or subfolder) | |
| **3D cube** appears when the model is ready (no NAS needed) | |
| Two stacked views, part not a flat 45° slab (true isometric) | |
| Black lines on white — no grey shading | |
| Through-holes as ellipses, not filled blobs | |
| Long shaft is a thin strip across 80 mm | |
| Print without a cube is still text-only, no wait | |
| Settings (**F2** / **PL** chip): language, BCM pins, ticks per tooth; survives restart | |
| Clicky encoder: rest is stable; highlight changes halfway to the next tooth | |

Windows office PC: double-click the exe (or `python -m fh6parse --gui` from a git clone). **Polski / English** radios at the top right (default English). Set **STEP folders…**. A wireframe cube means the STEP bitmap is ready. Windows print is still the browser dialog, not `/dev/usb/lp0`. If GitHub (frozen exe) or origin (git) has a newer build, a yellow **UPDATE** button appears after launch — one click, then the window restarts. Publish a new exe with `packaging\build_windows.bat` then `packaging\publish_windows.ps1`. Do not overwrite `fh6parse-kiosk.ini` next to the exe.

