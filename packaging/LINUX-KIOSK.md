# fh6parse Linux kiosk manual

Operator sheet (Polish, daily use only): **[LINUX-KIOSK-PL.md](LINUX-KIOSK-PL.md)**. Pi 5 pinout and wire poster: **[LINUX-KIOSK-WIRING.pdf](LINUX-KIOSK-WIRING.pdf)**. Hardware buy list (SKU / EAN if shops die): **[HARDWARE.md](HARDWARE.md)**. This file is the full English install / update manual.

**Version 1.4.1.** Raspberry Pi 5 kiosk: Waveshare **13857** in **portrait** (**600×1024**, panel native 1024×600 stood on the short edge), MUNBYN **P047**, USB `/dev/usb/lp0` print, isometric **line-art** STEP (stick `.stp` first), **D** vs T warnings, programmed cycle time and a per-tool share chart. Two knobs: **file** (list) and **mill** (scrolled mill list under the files, name also next to **v1.4.1**). Three 16 mm vandal print buttons under the screen, left→right **green LOAD** (operator slip), **yellow SET** (setter), **red RUN** (full ticket). The same three colour chips sit on the bottom of the panel. List, preview, and those chips use large high-contrast type. An optional fourth GPIO button sleeps and wakes the panel (leave it unwired). An optional Pi 5 **J2** switch is the hardware power button (not GPIO). Highlight a file to preview ops, cycle time, 3D ready, and the stacked isometric before print. Add mills in **settings** (**Add mill…**: name, rapids m/min, B/C rapid, tool-change time, tool length, optional max rpm, optional G53 ATC X/Y/Z, work offset X/Y/Z, travel min/max per axis). Tickets then show a labeled G53 rectangle of where the work offset may sit, and max Ø for a centred outside G41/G42. Screen language is **Polish** by default (**F2** / **C** / the **PL**·**EN** chip for English). A **wireframe 3D cube** next to a file means the STEP views are ready. Later git commits keep the **1.4.1** badge; the yellow **UPDATE** button then shows a short hash. The Windows / Linux office GUI is one report with a **section checklist** (no LOAD / SET / RUN presets). The same single-click yellow **UPDATE to …** bar appears under the mill/print row: frozen Windows exe against a GitHub Release (tag **vX.Y.Z** builds it), git checkout against origin.

Python **3.10+** is required (Bookworm ships 3.11). Use **Raspberry Pi OS 64-bit Desktop** (Bookworm or later). Pi 5 has no 32-bit OS.

The 40-pin header uses the **same BCM numbers as Pi 3/4**. GPIO on Pi 5 goes through the **RP1** chip: `RPi.GPIO` does **not** work. The kiosk uses gpiozero with **lgpio**. Still switch the desktop to **X11** (tkinter + `xset` blanking).

1. [What you need](#1-what-you-need)
2. [Hardware](#2-hardware)
3. [Software](#3-software)
4. [Boot to kiosk](#4-boot-to-kiosk)
5. [Daily use](#5-daily-use)
6. [Troubleshooting](#6-troubleshooting)
7. [Files on disk](#7-files-on-disk)
8. [Updating (1.4.1)](#8-updating-the-kiosk)
9. [Field test](#9-field-test)

---

## 1. What you need

| Item | Notes |
| --- | --- |
| Raspberry Pi 5 | Official **27 W USB-C** PSU (5 V / 5 A). Do not use a Pi 3 2.5 A supply. Do not power the printer from the Pi USB. |
| Raspberry Pi **Active Cooler** | Required in the closed kiosk box. Heatsink + PWM fan on the SoC FAN header. [Botland RPI-23925](https://botland.store/raspberry-pi-5-mounting-elements/23925-raspberry-pi-active-cooler-heatsink-fan-for-raspberry-pi-5-5056561803357.html). **§2.12**. |
| Pimoroni NVMe Base Duo (PIM704) | **Under** the Pi 5. PCIe FPC, not GPIO. [Botland](https://botland.com.pl/rozszerzenia-gpio-i-nakladki-hat-do-raspberry-pi-5/24851-plytka-rozszerzen-nvme-base-duo-do-raspberry-pi-5-pimoroni-pim704-769894025024.html). Do **not** use the Raspberry Pi M.2 HAT+ from the SSD kit. |
| Official Raspberry Pi NVMe **512 GB** (2230) | **Disk only** from [Raspberry Pi SSD Kit 512 GB](https://botland.com.pl/raspberry-pi-hat-nakladki-pci-express/25484-raspberry-pi-ssd-kit-512gb-zestaw-z-dyskiem-ssd-do-raspberry-pi-5-5056561805023.html) (RPI-25484). Unscrew it from the kit HAT+ and fit **slot A** on the Duo. Second Duo slot empty. |
| micro-HDMI cable | Pi 5 has two **micro-HDMI** ports. Use **HDMI0** (the port next to USB-C power) for the kiosk panel. **Clamp** USB-C and HDMI0 to the case. **No USB-C extension** on the 27 W PSU. |
| Case (3D print) | **PETG**, not PLA. Vents **above** the Active Cooler and **below** the Duo. **§2.13**. |
| Spare PCIe flex (drawer) | Pimoroni **PIM703** (35 mm) or **PIM702** (50 mm). The OS cable; clips break. |
| Waveshare 7″ HDMI LCD (C) **13857** | Panel native **1024×600**. The kiosk **stands on the short edge**, so the UI is **600×1024** portrait. HDMI0. Rotate the desktop (`xrandr --rotate left` or `right`) until `xrandr` shows **600x1024**. |
| DFRobot Fermion EC11 (file) | SEN0235. Phase **A** and **B** only. Shaft push (**C**) unused. Selects the NC file. |
| DFRobot Fermion EC11 (mill) | Second knob, same wiring. Cycles mills in settings / `kiosk.machine`. |
| Three 16 mm 5-pin vandal buttons | Momentary, ring LED **5 V**: **green LOAD**, **yellow SET**, **red RUN**. Mount **under the screen**, left→right matching the colour chips on the panel. |
| Spare momentary button | Optional. Same switch wiring as LOAD (NO → GPIO 25, C → common GND). Press blanks the panel; press again wakes. Leave unwired: the pin sits on the internal pull-up and never fires. Idle timeout, knobs, USB, and keyboard still sleep/wake. |
| Pi 5 J2 power switch | Optional. Momentary **NO** across the two **J2** (`PWR_BTN`) pads — same as the PCB power button. **Not** a 40-pin GPIO. Omit it: USB-C still boots when you plug in. |
| USB stick | FAT/exFAT/NTFS. Programs as `.nc` / `.NC` / `.tap` in the **stick root** only (not subfolders). |
| Panel USB 3.0 Type-A (27 mm) | Metal socket on the enclosure for that stick. [Allegro](https://allegro.pl/oferta/gniazdo-usb-3-0-typu-a-metalowe-do-zabudowy-na-pendrive-panelowe-27-mm-17741983408). Pigtail to a Pi **USB 3** port. **§2.11**. |
| MUNBYN P047 (ITPP047) | USB, 80 mm ESC/POS, auto-cutter. Own mains PSU. |
| Company STEP folder (optional) | NAS of `.stp` / `.step` if the stick has none. See **§3.7**. Stick copy is enough. |
| Network (optional) | Only for git install and later **UPDATE**. Printing works offline. |
| Keyboard / mouse | First-time setup, **settings** (language, mill / **Add mill…**, file and mill knobs, RUN / LOAD / SET / optional sleep pins, encoder ticks), SSH, or tap **UPDATE**. Not required for encoder + GPIO print. |

Default GPIO (**BCM** numbers, not header pin numbers):

| Function | BCM GPIO | Header pin |
| --- | --- | --- |
| File encoder A (CLK) | 17 | 11 |
| File encoder B (DT) | 27 | 13 |
| Mill encoder A (CLK) | 5 | 29 |
| Mill encoder B (DT) | 6 | 31 |
| RUN button (red) | 22 | 15 |
| LOAD button (green) | 23 | 16 |
| SET button (yellow) | 24 | 18 |
| Spare button (optional sleep/wake) | 25 | 22 |
| 3.3 V for encoder VCC | — | 1 or 17 |
| 5 V for button LED rings | — | 2 or 4 |
| GND | — | 6, 9, 14, 20, or 30 |

Change pins in **settings** (**F2** / **C** / **PL**·**EN**) or in `/etc/fh6parse-kiosk.ini`. Settings write `~/.config/fh6parse/ui.ini` (and the main ini if it is writable).

Land every GPIO / 3.3 V / 5 V LED wire on the **screw terminal board** on the 40-pin header, or on a **GPIO riser** if the cooler is in the way (**§2.9**). Do not also push Dupont onto the same header under that board.

---

## 2. Hardware

**Wiring poster (print this at the bench):** [LINUX-KIOSK-WIRING.pdf](LINUX-KIOSK-WIRING.pdf) — Raspberry Pi 5 top view, colour 40-pin map, panel layout, EC11 / vandal / J2, **screw terminal**, **NVMe Base Duo**, **panel USB**, **Active Cooler**, wire gauge and colours. Source: [LINUX-KIOSK-WIRING.html](LINUX-KIOSK-WIRING.html). The sections below are the same facts in text.

**Buy list (survives dead shop links):** [HARDWARE.md](HARDWARE.md) — SKU / EAN / size / substitute, **must do** and shop suggestions. Manufacturer PDFs in [hardware-archive/](hardware-archive/). Assemble checklist: **§2.13**.

### 2.1 Power and USB

- Pi 5 on the official USB-C 5 V / 5 A supply. USB-C on the Pi is **power only**. **Clamp** that plug and **HDMI0** to the case. Do **not** use a USB-C extension.
- Optional panel **power** is **J2**, not GPIO — **§2.8**. Without it, plug in USB-C and the Pi boots.
- P047 on its own supply; USB cable to a Pi **USB 2** port is **data only** if the printer has a separate PSU.
- USB stick through the **27 mm panel USB 3.0** socket — **§2.11**. Automount under `/media/<user>/…` or `/run/media/…` is enough; the kiosk polls those paths.
- Official **Active Cooler** on the SoC FAN header — **§2.12**. Seat that cable before the GPIO screw terminal.
- OS disk is the official Raspberry Pi **512 GB** NVMe on the **NVMe Base Duo under the Pi** — **§2.10**. Not GPIO. Not the kit M.2 HAT+.

### 2.2 GPIO rules

Pi GPIO is **3.3 V** (unchanged on Pi 5). Do not feed 5 V into A, B, or the button **signal** pins (C / NO / NC).

DFRobot EC11 (SEN0235) is **3.3–5 V**. Power it from the Pi: **VCC → 3.3 V** (header pin 1), **GND → GND**. Do not use the Pi 5 V pins for the encoder. If a clone only runs at 5 V, you still must not put 5 V on the Pi inputs (use a level shifter).

Encoder **C** (shaft click): leave unconnected. The kiosk does not read the push-switch.

### 2.3 16 mm 5-pin vandal buttons (no datasheet)

The Allegro 5 V ring-LED parts (and the common 16 mm LAS16 / Adafruit-style clones) have **five Faston tabs**, not two. The five functions are always the same even when the silk is missing:

| Tab | What it is |
| --- | --- |
| **C** | Switch common |
| **NO** | Normally open — closes to **C** while pressed |
| **NC** | Normally closed — opens from **C** while pressed (leave unused) |
| **LED +** | Ring anode (this listing is **5 V**, built-in resistor on most 3–6 V rings) |
| **LED −** | Ring cathode |

The switch and the LED are **separate circuits**. The kiosk only reads the switch (internal pull-up, press = GND). The rings are wired **always on** so the colours stay visible in a dim shop.

**Identify the tabs with a meter** (pin order on the back is not the same on every clone):

1. The two tabs that are a **diode**, not a click: that pair is **LED + / −**. One way around they drop ~1.8–3 V; the other way they are open. Tabs marked **+** / **−** (or a different colour / bent pair) are this pair.
2. The remaining three are the switch. **Unpressed:** **C–NC** beeps, **C–NO** is open. **Pressed:** **C–NO** beeps, **C–NC** is open. The tab that beeps in both tests (one at a time) is **C**.

Most likely rear view (looking at the **back**, tabs toward you) on these 16 mm 5 V rings:

```
     +         −          ← LED (often the two odd / marked tabs)

  NO     C     NC         ← 2.8 mm Faston. NC unused.
```

If that drawing does not match the part in your hand, trust the meter, not the sketch.

**Kiosk wiring (one button):**

```
GPIO (BCM, pull-up) ── NO
GND                 ── C
NC                     unused

5 V (header pin 2)  ── LED +
GND                 ── LED −
```

Same pattern on all three. Share **5 V** and **GND**. Do **not** jumper LED + onto a GPIO, and do **not** put 5 V on C / NO / NC.

| If | Then |
| --- | --- |
| Ring stays dark | Swap LED + and − |
| Ring is dim | Listing is 5 V — use header **5 V**, not 3.3 V |
| Ring gets hot | Add ~220 Ω in series with LED + (that clone has no built-in resistor) |
| Press does nothing, GPIO error | 5 V reached a GPIO — move the switch onto C/NO only, LED stays on 5 V |

**Panel layout** (buttons **below** the screen, left→right as you face it). The colour chips on the bottom of the UI are in this order:

| Left | Middle | Right |
| --- | --- | --- |
| **Green** LOAD (short / operator) | **Yellow** SET (setter) | **Red** RUN (full) |
| GPIO 23 / header 16 | GPIO 24 / header 18 | GPIO 22 / header 15 |

### 2.4 Wiring diagram (defaults)

Pi 5 40-pin header (same BCM layout as Pi 3/4), looking at the board with the USB-A / Ethernet ports down:

```
 3.3V  (1)  (2)  5V          ← encoder VCC to pin 1; LED rings to pin 2
 GPIO2 (3)  (4)  5V
 GPIO3 (5)  (6)  GND         ← shared GND (encoders + buttons + LED −)
 GPIO4 (7)  (8)  GPIO14
  GND  (9)  (10) GPIO15
GPIO17 (11) (12) GPIO18      ← file encoder A (CLK)
GPIO27 (13) (14) GND         ← file encoder B (DT)
GPIO22 (15) (16) GPIO23      ← red RUN           green LOAD
  3.3V (17) (18) GPIO24      ← yellow SET
GPIO10 (19) (20) GND
 GPIO9 (21) (22) GPIO25      ← optional sleep/wake (leave open if unused)
 …
 GPIO5 (29) (30) GND         ← mill encoder A (CLK)
 GPIO6 (31) (32) GPIO12      ← mill encoder B (DT)
```

DFRobot Fermion EC11 (SEN0235) silk:

| EC11 | Pi |
| --- | --- |
| VCC | pin 1 (3.3 V) |
| GND | pin 6 (GND) |
| A | pin 11 (GPIO 17) file, or pin 29 (GPIO 5) mill |
| B | pin 13 (GPIO 27) file, or pin 31 (GPIO 6) mill |
| C | not used |

If turning the **file** knob moves the highlight the wrong way, use **Reverse** on the file knob in settings (or `encoder_swap = true`, or swap A and B). Same for the mill knob (`encoder_mill_swap`). SEN0235 is **20 pulses** per turn (one detent per pulse). **Ticks per tooth** is shared: GPIO ticks from one rest valley to the next. Start at **2** if one click skips two files. The list (or mill) changes halfway, so a small wiggle at rest does not skip. The file list and the mill list **wrap**: past the last name is the first, past the first is the last.

### 2.5 Screen (Waveshare 13857)

The panel is a Waveshare **7″ HDMI LCD (C)** (SKU **13857**). The glass **stands on its short edge** (portrait). Panel timing is still **1024×600**; after rotation the desktop must be **600×1024**. The kiosk UI is that portrait size: file list on top, mill list under it (about a quarter of the former file band), preview + isometric below, LOAD / SET / RUN chips at the bottom. Windows / Linux GUI layout is unchanged. Plug micro-HDMI into **HDMI0** (next to USB-C). Leftover `width` / `height` in `/etc/fh6parse-kiosk.ini` or `ui.ini` are ignored.

On Raspberry Pi OS the default is **Wayland**. Switch to **X11** (tkinter + screensaver `xset` are unreliable on Wayland/labwc):

```
sudo raspi-config
```

- **Advanced Options → Wayland → X11**
- **System Options → Boot / Auto Login → Desktop autologin**
- Reboot

Then confirm the mode. **Screen Configuration** (desktop): HDMI **Orientation** left or right until the picture is upright and the size is **600×1024**. Apply and “OK”.

Or in a terminal after login:

```
xrandr --output HDMI-A-1 --mode 1024x600 --rotate left
```

If the image is upside-down, use `--rotate right`. `xrandr` with no arguments should show **600x1024**. Pi 5 KMS is usually `HDMI-A-1` for HDMI0.

To keep the rotation after reboot, set it in Screen Configuration or add the same `xrandr` line to `~/.config/autostart/` or `/etc/xdg/lxsession/LXDE-pi/autostart`.

Do not use legacy `display_rotate=` in `/boot/firmware/config.txt`. Pi 5 is KMS-only.

### 2.6 Printer (MUNBYN P047)

USB to the Pi. The kiosk sends **raw ESC/POS**: optional STEP bitmaps (`GS v 0`), then 48-column Font A, then cut. Do **not** print HTML or use a Windows GDI/POS-80 raster driver.

The app writes that blob to **`/dev/usb/lp0`** first (same as `open("/dev/usb/lp0", "wb").write(...)`). CUPS is not involved on a working Pi. Named CUPS (`lp -d munbyn -o raw`) is only a fallback if the USB node is missing or busy. There is no `lp` default-queue attempt.

If CUPS has already claimed the printer, the USB write fails with *Device or resource busy*. Stop or disable that queue (or CUPS) so `usblp` owns `/dev/usb/lp0`.

Before RUN / LOAD / SET the kiosk sends **DLE EOT** (real-time status, not printed) on that same node. Cover open, paper end, or cutter error stay on the status line (**Pokrywa otwarta** / **Brak papieru** / **Zacięcie drukarki**) and the ticket is not sent. If the firmware does not answer, print goes ahead as before.

### 2.7 Optional sleep / wake button (GPIO)

Not required. The shop kiosk blanks after `idle_seconds` (default 60) and wakes on either encoder, a USB stick, or a keyboard / mouse whether this button is fitted or not.

If you add a fourth vandal, wire it like LOAD:

```
GPIO 25 (header 22, pull-up) ── NO
GND (common with the other buttons) ── C
NC unused
LED + / − ── same 5 V / GND as the print rings, if the part has a ring
```

Press while the screen is on: DPMS off (panel black, Pi still running). Press again: wake. LOAD / SET / RUN still do not wake (avoids a ticket in the dark). An unconnected GPIO 25 stays high on the internal pull-up and never fires. If opening that pin fails, knobs and print buttons stay up.

Do **not** tie this GPIO to Pi 5 **J2**. Sleep is software DPMS; J2 is a real power switch.

### 2.8 Optional Pi 5 power button (J2)

Pi 5 already has a power button on the PCB. **J2** (two pads, silk **PWR_BTN**, between the RTC battery connector and the board edge) is the same switch in parallel. A panel button is a momentary **NO** across **those two pads only**.

| Do | Do not |
| --- | --- |
| NO across the two J2 pads | Tie J2 to GPIO 25, BCM 20, or GPIO GND |
| Leave J2 open if you skip the panel switch | Expect Pi 4 `WAKE_ON_GPIO` / `gpio-shutdown` on GPIO3 — that is not how Pi 5 power works |
| Keep the PCB button reachable for service | Put 5 V LED rings on J2 |

**Without J2 wired** the Pi behaves as stock: plug in USB-C and it boots. Halt from the desktop or `sudo halt` still works. Unplug / replug USB-C to start again.

**Short press** (OS running) generates Linux `KEY_POWER`. Raspberry Pi Desktop then shows Shutdown / Reboot — wrong on a shop panel. Optional, only if you want the PCB or J2 button to halt with no dialog:

```
sudo nano /etc/systemd/logind.conf
```

```
HandlePowerKey=poweroff
HandlePowerKeyLongPress=poweroff
```

Then `sudo systemctl restart systemd-logind` (or reboot). This affects the **onboard** button as well as J2. Omit the file and the kiosk still runs; you just get the Desktop dialog if someone presses the PCB button.

**Short press** after halt / PMIC standby boots again. **Hold** a few seconds is a hard cut.

Optional EEPROM (lowest power after halt; still optional):

```
sudo -E rpi-eeprom-config --edit
```

```
POWER_OFF_ON_HALT=1
```

Then a clean halt puts the PMIC in standby; J2 or the PCB button wakes it. USB-C unplug / replug still applies 5 V and boots **unless** you also set `WAIT_FOR_POWER_BUTTON=1`. **Do not set `WAIT_FOR_POWER_BUTTON` unless J2 is on the panel** (or the PCB button stays reachable). Without a power button that flag leaves the Pi sitting dead after a power cut.

fh6parse does not read J2. 5 V LED rings on the 40-pin header stay on after halt unless you switch that 5 V yourself.

### 2.9 GPIO screw terminal and wires

**GPIO adapter (Pi end).** GPIO screw terminal board — [Kamami 588019](https://kamami.pl/prototypowanie-raspberry-pi/588019-modul-hat-ze-zlaczami-srubowymi-dla-raspberry-pi-5906623475650.html) (same 40-pin screw block as the 52Pi listing). Sold for Pi 4B / 3B+ / Zero; the Pi 5 **40-pin header is the same**, pin 1 still at the USB-C end. Press the female 2×20 onto the header. Fit the kit **M2.5 brass standoffs** so vibration cannot walk it off. Official Pi 5 cooler stays on the SoC; this board only occupies the GPIO strip. Seat the **FAN** cable first. If the terminal still will not sit (cooler, FAN plug, or case lid), put a **40-pin GPIO riser** (stacking header, extra-tall female-to-male) on the Pi first, then the screw terminal on the riser. Same pin 1 / BCM map — do not rotate the riser. The **NVMe Base Duo** is **under** the Pi (**§2.10**), not stacked on this header. If the parcel is the larger LED HAT (52Pi EP-0129), it can fight that cooler — keep the cooler, do not stack a second HAT.

Silk is **BCM**: `IO17` = GPIO 17, not header pin 17. Confirm pin 1 before the first screw. Leave **GPIO 2 / 3** (header 3 / 5, I²C1) empty for a future Qwiic keypad. **J2 is not on this board.** Colour card: [LINUX-KIOSK-WIRING.pdf](LINUX-KIOSK-WIRING.pdf) page 4.

Three looms, not one bag of jumper wires. GPIO sense, LED rings, and Pi power must never share a conductor that can put 5 V on a BCM pin. **Do not** use loose Dupont jumper packs as the finished harness.

**Buy**

| Circuit | Wire | Ends |
| --- | --- | --- |
| Encoder A/B, button **NO** (3.3 V sense) | **24 AWG** stranded (0.25 mm²), PVC or silicone | Screw on the 52Pi board; Dupont or solder at the EC11 |
| Encoder **VCC 3.3 V**, common **GND** | **22 AWG** stranded (0.34 mm²) | Screw on 3.3 V (pin 1 / 17) and GND |
| LED **+ 5 V** and LED **−** | **22 AWG** stranded | Screw on 5 V (pin 2) / GND; insulated **2.8 mm Faston** on the vandal |
| Optional **J2** power | **26–28 AWG**, keep under 20 cm | Solder or JST-SH 1.0 2-pin on **J2 only** |
| Future Qwiic keypad | Official **Qwiic 4-pin** cable | Do not steal SDA/SCL screws for buttons |

**24 AWG** is the default for every GPIO run under ~40 cm. **22 AWG** for 3.3 V / 5 V / GND so a 2.8 mm Faston crimp holds. Terminals take about **16–26 AWG**; stay 22/24 in the loom. Stranded only (vibration). Bootlace ferrule on the screw end; do not tin a blob. Silicone is nicer next to the Pi 5 cooler; PVC is fine in the rest of a 3D-printed case.

**Colour** (so a meter is not required at 2 a.m.)

| Colour | Net |
| --- | --- |
| Black | GND (one net: knobs, C tabs, LED −) |
| Orange | 3.3 V encoder VCC (pin 1 / 17) |
| Red | 5 V LED + **only** (pin 2) |
| Blue / light blue | File encoder A / B |
| White / grey | Mill encoder A / B |
| Green | LOAD NO (BCM 23) |
| Yellow | SET NO (BCM 24) |
| Brown | RUN NO (BCM 22) — **not** red |
| Violet | SLEEP NO (BCM 25), if fitted |
| Grey twisted pair | J2 only |

Do not use the same red for RUN and for LED +. That mix-up is a dead Pi.

**Terminations.** Pi: screw terminal on the 40-pin header, or on a **GPIO riser** if it will not fit next to the cooler (standoffs, strip ~5 mm, ferrule). Strain-relieve the bundle to the case, not to the board. Vandal: insulated 2.8 mm Faston females, **crimped** (do not solder on the switch). Leave **NC** empty. EC11: Dupont or solder on the pin row; leave shaft **C** open. J2: two short flying leads across the pads only — never a screw on the GPIO block.

**Length.** GPIO A/B and button NO **under ~40 cm**. Twist each encoder pair. Do not tape encoder wires along the 5 V LED bundle or a USB 3 cable. Star GND at header pins 6 / 9 / 14 — do not daisy LED − through a switch C. LED rings are tens of mA; pin 2 is enough. The official **USB-C 5 V / 5 A** cable is the only high-current wire. Do not jumper the NVMe Duo extra 5 V pads onto pin 2 unless a drive actually browns out (**§2.10**).

### 2.10 NVMe Base Duo (PCIe, not GPIO)

Pimoroni **NVMe Base Duo** (PIM704) — [Botland](https://botland.com.pl/rozszerzenia-gpio-i-nakladki-hat-do-raspberry-pi-5/24851-plytka-rozszerzen-nvme-base-duo-do-raspberry-pi-5-pimoroni-pim704-769894025024.html). Two M.2 **M-key** NVMe slots (2230–2280) on the Pi 5 **PCIe FPC** (next to the PCB power button). It is not a 40-pin HAT. The 52Pi screw terminal, official cooler, and J2 stay on **top** of the Pi.

**Mount under the Pi.** Kit 12 mm M2.5 standoffs through the four Pi holes. Power **off** first. FPC: wider **ADDON** end into the Duo (grey clip flips up; writing faces down into the socket), **RPI 5** end into the Pi (brown clip slides ~1 mm). Pirate logo / writing faces out when folded. Fold the Duo under the Pi like a hinge — do not crease the flex. Assembly: [Pimoroni getting started](https://learn.pimoroni.com/article/getting-started-with-nvme-base-duo).

The flex can cover the **microSD** slot. Insert a rescue SD **before** folding. Shop kiosk: boot from **slot A** NVMe once firmware is **2024-05-17 or newer**:

```
sudo apt update && sudo apt upgrade
sudo reboot
sudo rpi-eeprom-update
lsblk
```

`lsblk` must show `nvme0n1`. Then Raspberry Pi Imager onto that disk, and `raspi-config` → Advanced Options → Boot Order → **NVMe/USB Boot**. Git clone in **§3.2** then lives on that disk. USB stick still carries `.nc` / `.stp`.

**Disk:** official Raspberry Pi **512 GB** NVMe, **2230** (22 × 30 mm), M-key, TLC, 3.3 V, max **2.8 W**. Buy the [Raspberry Pi SSD Kit 512 GB](https://botland.com.pl/raspberry-pi-hat-nakladki-pci-express/25484-raspberry-pi-ssd-kit-512gb-zestaw-z-dyskiem-ssd-do-raspberry-pi-5-5056561805023.html) and **take only the SSD**. The kit HAT+, 16 mm GPIO spacers, and screws stay in the drawer — that HAT+ would sit on the 40-pin header and fight the 52Pi terminal and cooler. On the Duo, the SSD is already on the official HAT+: undo the tiny M2, plug it into **slot A**, and use the Duo’s **2230** standoff hole (closest to the socket), not 2280.

One drive. Leave slot B empty (not RAID, not required for fh6parse). Stay **PCIe Gen 2** even though the Pi SSD is rated Gen3×4; do not set `dtparam=pciex1_gen=3`. Official **27 W** PSU. Extra 5 V pads on the Duo stay unused at 2.8 W.

### 2.11 Panel USB 3.0 (pendrive)

Metal **USB 3.0 Type-A** socket, **27 mm** panel cutout — [Allegro](https://allegro.pl/oferta/gniazdo-usb-3-0-typu-a-metalowe-do-zabudowy-na-pendrive-panelowe-27-mm-17741983408). Screw it onto the 3D-printed enclosure (nut on the inside). The operator plugs the stick into the front; a short USB 3 pigtail runs to a Pi **USB 3** port (the blue pair next to Ethernet). Not GPIO. Not power for the Pi or the P047.

Keep the P047 on a **separate** Pi USB-A (USB 2 is enough). Do not daisy the printer through this panel socket. Strain-relieve the pigtail to the case, not to the Pi header. Do not tape it along encoder A/B. The kiosk still automounts under `/media` / `/run/media` — no extra driver.

### 2.12 Active Cooler

Official Raspberry Pi **Active Cooler** (heatsink + PWM fan) — [Botland RPI-23925](https://botland.store/raspberry-pi-5-mounting-elements/23925-raspberry-pi-active-cooler-heatsink-fan-for-raspberry-pi-5-5056561803357.html). Pi 5 only. Clip the heatsink onto the SoC; plug the **4-pin** lead into the **FAN** header next to GPIO pin 1 (VCC, GND, PWM, tach). Firmware drives the fan; fh6parse does not. Compatible with the NVMe Duo **under** the Pi. Seat this cable **before** the GPIO screw terminal. If the terminal still will not clear the cooler, use a GPIO riser (**§2.9**). The spring clips are not meant for repeated removal. Print the case in **PETG** with vents above this fan and below the Duo (**§2.13**).

### 2.13 Must do and shop suggestions

Same tables: [HARDWARE.md](HARDWARE.md). The parts list is coherent; shop failures are **connectors and heat**, not missing SKUs.

**Must do at assemble**

| Do | If you skip it |
| --- | --- |
| Never put **5 V** on a BCM pin. LED rings on pin 2 only. RUN is **brown**, not red. | Dead Pi |
| Seat the **PCIe flex** with power off, both clips locked, no crease. The four Duo standoffs carry the sandwich. Keep a spare **PIM702 / PIM703** in the drawer. | Black screen; OS is on that cable; SD slot often blocked |
| **Clamp USB-C and micro-HDMI0** to the case. Official 27 W cable only — **no USB-C extension** (PD 5 A dies). | Undervoltage / blank panel after vibration |
| Screw-terminal silk is **BCM** (`IO17` = GPIO 17, not header pin 17). Pin 1 at USB-C. Do not rotate a riser. | 3.3 V on a GPIO or one-pin-over short |
| **PETG** case, vents **above** the Active Cooler and **below** the Duo. Do not pack foam on the blower. | Thermal throttle / PLA warp |
| Strain-relieve the GPIO bundle and the USB 3 pigtail to the **case**, not the Pi. Thick boss + nut/washer on the 27 mm USB hole. | Walked header / cracked print |

**Suggestions (first month in the shop)**

- Keep the USB 3 pigtail off the encoder loom (USB 3 is noisy).
- Solder or glue the EC11 Dupont end; the Pi end is already screws.
- Cable-tie a GPIO riser so it cannot lift.
- Threadlocker on the 2230 M2; check after a week of vibration.
- Dummy USB plug when idle; coarse foam on the cooler intake (CNC dust).
- 27 W brick close to the Pi.

Leave unless it bites: J2 halt, UPS, slot B clone, PCIe Gen 3, RAID. Git **UPDATE** does not rewrite the boot partition; a power cut during `apt` / EEPROM still can.

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

Expect `fh6parse 1.4.1+……` (package number plus git short SHA). If the number is older, this clone is behind — `git fetch && git pull --ff-only` then check again (**§8**).

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

The one-file ARM tarball does not bundle the CAD stack, so **§3.7** pictures are git-checkout only. There is no **UPDATE** button and `--update` refuses this install. To get the 1.4.1 shop update path later, switch to the git checkout above.

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
| `width` / `height` | 600 / 1024 | Portrait (panel stood on the short edge). Fixed in the app; leftover ini / `ui.ini` values are ignored. |
| `encoder_clk` / `encoder_dt` | 17 / 27 | File knob BCM pins (EC11 **A** / **B**). Change in **settings** or here. |
| `encoder_mill_clk` / `encoder_mill_dt` | 5 / 6 | Mill knob BCM pins (header 29 / 31). |
| `encoder_swap` / `encoder_mill_swap` | false | Reverse file knob / mill knob if the list moves the wrong way. Same as **Reverse** in settings. |
| `encoder_steps` | 1 | GPIO ticks from one tooth valley to the next (shared). DFRobot EC11 is usually **2**. Highlight / mill changes at half a tooth so rest is stable. |
| `button_run` / `button_load` / `button_set` | 22 / 23 / 24 | Red RUN / green LOAD / yellow SET. Old `button_full` / `button_min` still read. |
| `button_spare` | 25 | Optional sleep/wake. Press blanks the panel; press again wakes. Unwired pin never fires. |
| `button_delay` | 2 | Seconds to ignore LOAD / SET / RUN after a ticket so a double press does not print two slips. `0` = no wait. Change in **settings**. |
| `printer_device` | /dev/usb/lp0 | USB printer node (**tried first**) |
| `printer_queue` | (empty) | Optional CUPS name; used only if the USB node fails. Empty = never call `lp`. |
| `scan_depth` | 1 | USB root only. Raise to search subfolders. |
| `extensions` | `.nc,.tap` | File types (case-insensitive) |
| `extra_roots` | (empty) | Extra folders to list, comma-separated (for testing) |
| `model_roots` | (empty) | Optional company `.stp` folders. USB stick is searched first. See **§3.7**. |
| `language` | `pl` | Screen language: `pl` (default) or `en`. Change on the kiosk in **settings** (**F2** / **C**, or click **PL** / **EN**). Mill is on that first page; ticket ticks, GPIO, and knobs are submenus. Stored in `~/.config/fh6parse/ui.ini` (and in this ini if it is writable). |
| `machine` | `default` | Id of the mill used for cycle time (`[machine.<id>]` below). Change in **settings**. |
| `fullscreen` | true | Shop display. Escape once exits fullscreen. |

Add one `[machine.<id>]` section per mill, or use **Add mill…** on the Windows/Linux GUI and in kiosk **settings**. Built-in **Default mill** is 20 m/min rapids and 0 s tool change until you pick another. Keys:

| Key | Default | Meaning |
| --- | --- | --- |
| `name` | the id | Label on the kiosk, Windows GUI, and tickets |
| `rapid_mm_min` | 20000 | Linear G0 rate (mm/min) for XYZ time |
| `rotary_deg_min` | 5400 | B/C G0 rate (deg/min) |
| `tool_change_s` | 0 | Seconds added at every Txx M6 (carousel swap only) |
| `max_rpm` | (omit) | Spindle limit. A tool’s S above this prints a WARNING on LOAD / RUN. |
| `atc_x` `atc_y` `atc_z` | (omit) | That mill’s tool-change position in G53 mm (one field per axis). B and C are **0**. Old `atc_b` / `atc_c` still read. |
| `offset_x` `offset_y` `offset_z` | (omit) | Typical vise/table work origin in G53 mm (G54, G55, … — the same machine point). B and C are **0**. Old `g54_x` / `g54_y` / `g54_z` still read. |
| `tool_length_mm` | 0 | Approximate stick-out (Z only). Haas H is a register, not mm. |
| `x_min` `x_max` `y_min` `y_max` `z_min` `z_max` | (omit) | Machine travel envelope in G53 mm, one field per axis and limit. Tickets then show where the work offset may sit so programmed XY stays inside travel. |

If ATC and offset XYZ are all set, cycle time uses one G53 pose: work rapids convert through the stored offset + tool length; at Txx M6 the finishing tool rapids Z then XY to that mill’s ATC (B0 C0), then `tool_change_s` on the new T. A program that already `G53`’s to the ATC is not charged twice. Omit the keys to keep the older estimate (Default mill).

If XY travel is set, the ticket adds a labeled rectangle of allowed work-offset origin (G53 mm): four corners, center, max Ø for centred outside G41/G42 (the shorter leftover), and a warning if the stored offset is outside or the work is larger than travel. Needs Pillow for the PNG; numbers still print without it.

Example:

```
machine = vf-4ss

[machine.vf-4ss]
name = Haas VF-4SS
rapid_mm_min = 25400
rotary_deg_min = 5400
tool_change_s = 2.8
atc_x = -750
atc_y = -20
atc_z = 0
offset_x = -400
offset_y = -250
offset_z = -400
tool_length_mm = 120
x_min = -1270
x_max = 0
y_min = -508
y_max = 0
z_min = -635
z_max = 0
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

The shop screen is **Polish** unless `language = en` is set. Open **settings** with the keyboard or mouse (not the encoder): **F2** or **C**, or click the **PL** / **EN** chip next to the version. Pick **Polski** or **English**, the mill (rapids, tool-change time, optional G53 ATC / work offset / tool length / travel from `[machine.<id>]` in this ini; the mill name also sits next to the version chip and the mill knob cycles it), **Add mill…** to create a new mill (written to `~/.config/fh6parse/ui.ini`), a **LOAD | SET | RUN** tick matrix for ticket content (Reset LOAD / SET / RUN restore the factory packs; G68 / D vs T / S max / late offset / G95 / travel-too-big always print), BCM pin numbers for file A / B, mill A / B, green LOAD / yellow SET / red RUN / optional sleep, knob **Reverse**, **ticks per tooth**, and **print wait** after a ticket (GPIO ticks from one rest valley to the next; the highlight or mill changes halfway so a wiggle at rest does not skip; file and mill lists wrap). Language, mill, GPIO, and `report_load` / `report_set` / `report_run` are written to `~/.config/fh6parse/ui.ini` (user `kiosk` can write this even when `/etc/fh6parse-kiosk.ini` is root-owned) and, if permitted, into the main ini. Pin changes take effect immediately (GPIO is reopened). **Esc** closes the mill form first, then settings; the next **Esc** still leaves fullscreen. The file encoder or a GPIO print button closes settings without printing / skipping a file. The mill encoder keeps settings open and changes the mill.

| Input | While awake | While screensaver |
| --- | --- | --- |
| Arrows, mouse wheel, click a file | Move highlight | First event only wakes |
| **F** / **M** / **S** | Print RUN / LOAD / SET | Ignored (no ticket); another key or click wakes |
| GPIO RUN / LOAD / SET (red / green / yellow) | Print | Ignored (no ticket, stays black) |
| GPIO spare (optional) | Sleep (black panel) | Wake |
| Yellow **UPDATE to …** / **U** | One tap: pull, then restart kiosk | Wake first, then tap |
| **F2** / **C** / click **PL**·**EN** | Open or close settings (language, report ticks, pins, encoder ticks) | Wake first |
| In settings: arrows / wheel / **Polski**·**English** | Switch language | — |
| In settings: **+** / **−** | BCM pins, ticks per tooth, and print wait | — |
| **Esc** | Close settings, else leave fullscreen, then close | Wake, then Esc again leaves fullscreen |

Plug in a USB stick with `.nc` files; the list should fill by itself.

Desktop autostart of the kiosk is in the next section. Until then, Escape leaves fullscreen, Escape again closes the window.

### 3.7 STEP models on the ticket

Optional. The kiosk looks for a matching `.stp` / `.step` **on the USB stick first** (same folder as the `.nc`, then subfolders on that stick). No NAS is required. Company folders in `model_roots` are a fallback if the stick has no match.

SET and RUN tickets can show two opposite **true isometric** views (45° then ~35.3° — look along the cube diagonal), as **visible edges only** (silhouette + sharp creases, no shading). Through-holes draw as ellipses (near rim, and the far rim only where you can see through). The longest 3D axis is laid across the 80 mm width (~512 dots); height is cropped to the part, so a long thin shaft is a thin strip, not a metre of paper. A bulky part is capped (~30 mm of paper per view). Print never waits for a model. After an update, delete `/tmp/fh6parse-models` so old shaded bitmaps are not reused.

**1. USB (usual shop path).** Put the STEP file next to the program, or in a subfolder on the same stick:

```
D0134078.nc
D0134078_Rev03.stp
```

or `D0134078.nc` plus `cad/D0134078_Rev03.stp`. The kiosk indexes the stick when it is inserted. Matching rules are **§3.7 step 4**. CAD extra (**step 3**) is still required to draw the picture.

**2. Optional company CAD folders** in `/etc/fh6parse-kiosk.ini` if the stick has no STEP. Several roots are allowed (comma or `:` / `;`). Subfolders are searched. A file on the stick always wins over the NAS.

```
model_roots = /mnt/fh6parse-cad
```

fh6parse **only reads** that folder (list `.stp` / `.step`, open for the isometric). It never creates, overwrites, or deletes files there. Rendered bitmaps go to `/tmp/fh6parse-models` on the Pi (or `%TEMP%\fh6parse-models` on Windows). Reports are not written next to company files. CIFS is mounted **read-only**, so the kernel also refuses writes. Network shares (CIFS/NFS) are never treated as a USB stick.

**Easy mount of the office Z: drive** (plug the Pi into company Ethernet). On a Windows PC, `net use Z:` shows the UNC (example `\\fileserver\Dokumentacja`). Then on the Pi:

```
sudo apt install -y cifs-utils
sudo bash /home/kiosk/fh6parse/packaging/connect-windows-share.sh //fileserver/Dokumentacja --guest
```

Domain account (more common):

```
sudo bash /home/kiosk/fh6parse/packaging/connect-windows-share.sh //fileserver/Dokumentacja --user kiosk --domain COMPANY
sudo nano /etc/fh6parse-cad.cred
```

Put the password on the `password=` line, `chmod 600`, then `sudo mount /mnt/fh6parse-cad`. The script writes a **read-only** `fstab` line with `x-systemd.automount`: when the cable is unplugged the kiosk still starts; when you plug in, the share appears on first use (STEP cubes fill in within a minute). Template: `packaging/fh6parse-cad.cred.example`.

Manual equivalent:

```
sudo mkdir -p /mnt/fh6parse-cad
# /etc/fstab (one line):
# //fileserver/Dokumentacja /mnt/fh6parse-cad cifs credentials=/etc/fh6parse-cad.cred,ro,uid=kiosk,gid=kiosk,iocharset=utf8,file_mode=0444,dir_mode=0555,_netdev,nofail,x-systemd.automount 0 0
```

If the share is down, the ticket is still text only.

On **Windows**, pick **STEP folders…** once. Prefer the UNC (`\\fileserver\Dokumentacja`) so it still works if the letter is not Z:. That path is `model_roots` in `fh6parse-kiosk.ini`. The GUI will not save reports into that folder.

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

**5. On the screen**, a small **wireframe 3D cube** appears next to the file when the bitmap is rendered and ready (same icon as the legend under the title — the same visible-edge isometric language as the ticket). The **stacked isometric** itself is shown **under the mill list** on the kiosk (and above the Windows GUI report) so a wrong STEP can be caught before print. The walk and render run in the background for every USB file in the list. Cache: `/tmp/fh6parse-models`.

On **Windows**, the GUI also searches next to the opened NC file. **STEP folders…** is the company-share fallback (prefer `\\server\share`, not only Z:). Paths are saved as `model_roots` in `fh6parse-kiosk.ini` next to the exe. fh6parse will not write reports into that folder. The Windows one-file build bundles the CAD stack; print still works if a model is missing.

---

## 4. Boot to kiosk

Copy the unit and enable it. The service assumes user `kiosk`, display `:0`, and Desktop autologin. If `model_roots` is on a company share, use the read-only automount in **§3.7** (`/mnt/fh6parse-cad`). The kiosk starts even if the cable is unplugged; cubes appear after the share is up. The sudoers line from **§3.2** must exist if you want the **UPDATE** button to restart the unit.

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
2. Insert the USB stick. `.nc` / `.tap` files in the stick **root** appear. The count line shows **Można wyjąć** / **Safe to remove** when the kiosk is not reading the stick — wait for that before unplugging. **Czytanie pendrive — czekaj** / **Reading USB — wait** means preview parse or a STEP copy from the stick is still running.
3. Turn the **file** encoder to highlight a file (past the last name wraps to the first). The **band under the list** shows each operation’s tool count and cycle time, whether the STEP views are ready, and the isometric when it is. Check OP1 vs OP2 here before printing. If that `.nc` is overwritten on the stick (same name, new bytes), preview reloads from disk — wait for **Reading…** to finish before RUN / LOAD / SET. The mill name sits under the title; turn the **mill** knob to change mill (same wrap as **Add mill…** / settings).
4. **Green LOAD** (left under the screen) — factory operator slip: file / program / units, tool list with T / H / D / S / Min Z and load boxes, always-on safety, sign-off. No mill, no cycle chart, no each-Txx-M6 dump, no offset box, no STEP. Change ticks in **F2**.
5. **Yellow SET** (middle) — factory setter slip: file / program, mill name, STEP when ready, offset rectangle + Ømax + Z window, cycle time (no share chart), programmer `!` notes, always-on safety, sign-off.
6. **Red RUN** (right) — factory full slip: STEP, offset block, ops, cycle + time split (G0 / cut / rot / canned / probe / ATC stacked per T), tool list, each Txx M6 / M00, extra warnings. No load boxes, no sign-off. The three colour chips on the bottom of the screen sit in this same left→right order. After a ticket, LOAD / SET / RUN are ignored for **print wait** (default 2 s; **Czekaj przed następnym biletem** / **Wait before the next ticket**) so a second press does not cut two slips.
7. If the status line says **Pokrywa otwarta** / **Printer cover open**, **Brak papieru** / **No paper**, or **Zacięcie drukarki** / **Printer jam**, fix the P047 first. RUN / LOAD / SET will not cut a blank slip. Those messages also appear on their own while idle (polled about every 2 s).
8. If there is no cube, print anyway. The slip is text only. The chip next to the cube legend says why: **3D ready**, **searching…** / **szuka…** (looking for a `.stp`), **rendering…** / **liczy…** (drawing a match), **no STEP** / **brak STEP**, **Z: off** / **Z: wył.** (company share down), or **no CAD** / **brak CAD** (install `[models]`).
9. Status after a good print: **`device:/dev/usb/lp0`**. If it says `lp:…`, CUPS took the job — **§3.5**.
10. **WARNING:** lines: `H{n} does not match T{tool}` on G43, `D{n} does not match T{tool}` on any D, `G95 still active…` if feed-per-rev was not cancelled with G94 before the next tool (or M30), empty-pocket (`Txx M6` with no motion) except the **last** tool change (spindle prep), `G55 after operation started (L…)` if G54–G59 appears after the first Txx M6 or M97/M98 (offset belongs in the file preamble only), `S{n} exceeds mill max {rpm}` when that mill’s `max_rpm` is set, and `G68 T12 L40 to G69 T15 L80` / `G68 T12 L40 without G69` when coordinate rotation is used (cancel with G69 before M30). Matching H/D stay quiet. Comments with `!` print as **Programmer notes**.
11. After **60 seconds** with no encoder movement and no new USB, the screen goes black.
12. Wake: either encoder, inserting a USB stick, a **keyboard / mouse**, or the optional spare GPIO. The first encoder step, key, or click only wakes; it does not skip a file or print. GPIO print buttons while asleep stay ignored. Spare while awake blanks the panel (same as the 60 s idle). No spare button: idle timeout and knobs still work.
13. Settings: **F2** / **C** or the **PL**/**EN** chip (mouse) — **§3.6**. The file encoder does not open settings. Mill picker, **Add mill…**, pins, knob reverse, ticks per tooth, and print wait are on that panel.
14. Print buttons **do nothing** while the screen is asleep (avoids accidental tickets).
15. Current version is **v1.4.1+……** at the top right (mill name is next to it). The suffix is the git short SHA of this checkout. If the Pi is on the network and origin is ahead, a yellow **UPDATE to x.y.z** (or a git hash if the number is still 1.4.1) appears **after this boot’s check**. It does **not** update by itself. One tap installs and **restarts** the kiosk (sudoers in **§3.2**). Print still works until you tap it.

Preview parse runs when a file is highlighted (idle, not on RUN / LOAD / SET). STEP matching and rendering run in the background and must not delay the ticket.

---

## 6. Troubleshooting

| Symptom | What to check |
| --- | --- |
| `GPIO off: …` on the status line | `python3-gpiozero` and `python3-lgpio` installed (not `python3-rpi.gpio` on Pi 5); user in group `gpio`; pins not already claimed. |
| Knob does nothing | File knob defaults 17/27, mill knob 5/6. A/B (CLK/DT) on the BCM numbers shown in settings; common GND; 3.3 V VCC. Try **Reverse** for that knob. |
| Mill name does not change | Mill knob BCM 5/6 (header 29/31). Need more than one mill in settings. `encoder_mill_swap` if it turns the wrong way. |
| Knob skips or jitters at rest | Raise **Ticks per tooth** so the valley is several GPIO ticks wide; highlight only changes halfway to the next tooth. Shorter wires; module decoupling. The kiosk also sets a short encoder `bounce_time` for Pi 5. Loose jumper packs walk off the header — land wires on the screw terminal (**§2.9**) and fit the brass standoffs. Terminal will not seat next to the cooler: 40-pin GPIO riser, then the terminal on top. |
| Buttons print on press and release | Use momentary **NO** to GPIO and **C** to GND. Leave **NC** and the LED tabs off the GPIO. Not a latching switch. Raise **print wait** (`button_delay`) if two tickets still come out. |
| **Czekaj przed następnym biletem** / **Wait before the next ticket** | Normal after a print. Default 2 s (`button_delay`). Settings **+** / **−**. |
| Ring LED dark | LED + to header **5 V** (pin 2), LED − to GND. Swap +/− if it stays dark. Dim on 3.3 V is expected on the 5 V rings. |
| Pi dies / GPIO error after wiring LEDs | **5 V reached a GPIO.** LED stays on pin 2; C / NO / NC must never see 5 V. |
| List stays on Insert USB / Włóż pendrive | Stick seated in the **panel** socket? Pigtail in a Pi **USB 3** port? `ls /media` / `ls /run/media`. Format FAT32. Files ending `.nc` or `.tap` in the stick **root**. |
| Preview does not match the stick file | Same name overwritten? Wait until **Reading…** clears. Reload uses mtime **and** size (FAT 2 s). Do not yank during **Reading USB — wait**. |
| Yanked stick, list frozen / cube stuck | Wait for **Safe to remove** next time. Plug back in. `rm -rf /tmp/fh6parse-models` if pictures are from a half-copy. |
| `printer failed` | `ls -l /dev/usb/lp0`; user `kiosk` in group `lp`; test the Python write in **§3.5**. *Permission denied* → log out after `usermod`. *Busy* → CUPS still owns the printer (`sudo systemctl disable --now cups`). |
| **Brak papieru** / **Pokrywa otwarta** / **Zacięcie drukarki** | Load paper, close the cover, or clear the cutter. RUN / LOAD / SET is blocked on purpose. If the P047 never answers DLE EOT, print still goes through (no false alarm). |
| Blank slip / cut with no text | Paper was likely already out or the cover was open *before* this build. Confirm the status line. |
| Garbage on the slip | CUPS grabbed the job. The kiosk writes `/dev/usb/lp0` first; disable CUPS (**§3.5**). Status must show `device:/dev/usb/lp0`, not `lp:…`. |
| Ticket does not cut | Cutter empty/jammed. Status should show **Zacięcie drukarki** / **Printer jam**. App already sends ESC/POS cut (`GS V`) when status is OK. |
| Screen never sleeps | `idle_seconds = 0`, or encoder bouncing. Still on Wayland? Switch to X11 so `xset` works. Optional spare GPIO also blanks even when idle is 0. |
| Optional sleep button does nothing | Unwired is normal. If fitted: NO to GPIO 25, C to common GND, same as LOAD. Screen still blanks after 60 s without it. |
| Keyboard/mouse do nothing | Plug into the Pi USB-A; X11 picks them up. Click or press a key — the kiosk claims focus. **F2** / **C** opens settings. **Esc** closes settings, then leaves fullscreen. GPIO print buttons still do not wake the screensaver. |
| Language resets to Polish after you picked English | Stored in `/home/kiosk/.config/fh6parse/ui.ini`. Pick **English** again in settings. **UPDATE** does not delete that file. Pins, mill, and ticks live in the same overlay. |
| **Add mill…** missing / mill list is only Default | Clone is older than this pull. Settings → **Add mill…**. Saved in `ui.ini` (`[machine.<id>]`). Travel keys `x_min`…`z_max` print the offset rectangle. |
| Screen stays in English and **F2** does nothing | Wake first if the screen is black. Click the **EN** chip next to **v…**. Encoder never opens settings. |
| Black screen immediately | Desktop blanking plus app DPMS. Disable LXDE idle blank; keep kiosk `idle_seconds = 60`. |
| Wrong aspect / clipped UI | `xrandr` must show **600x1024** (rotated). The app is portrait: files, then mills, then isometric. If you still see 1024x600, the desktop is landscape and the right side is cut off. Try `--rotate left` then `--rotate right`. Pi 5 output is often `HDMI-A-1`. |
| Service dead, UI never starts | `echo $DISPLAY` in a desktop terminal should be `:0`. `raspi-config` → X11, desktop autologin. `journalctl -u fh6parse-kiosk`. Unit `User=` must be `kiosk`. |
| Pi stays on after halt / no panel power | J2 is optional. USB-C unplug/replug boots. Do not set `WAIT_FOR_POWER_BUTTON=1` unless J2 is wired. PCB power button is the same as J2. See **§2.8**. |
| Undervoltage / random reboots | Official 27 W PSU, **no USB-C extension**, cable clamped. A phone charger or Pi 3 supply is not enough. The Pi 512 GB SSD is 2.8 W max; LED rings stay on the same PSU. |
| `lsblk` has no `nvme0n1` | Power off. Reseat both FPC clips: **ADDON** on the Duo, **RPI 5** on the Pi. No crease in the flex. Firmware `sudo rpi-eeprom-update` dated 2024-05-17 or later. Official Pi **2230** SSD in Duo **slot A** (2230 hole, not 2280). Do not leave it on the kit M.2 HAT+. Spare flex: PIM702 / PIM703. |
| Blank / flickering LCD | micro-HDMI0 walked off — clamp it. Port next to USB-C. |
| Cannot reach the microSD slot | Normal with the Duo **under** the Pi. Boot from NVMe. Rescue SD goes in **before** folding the flex. |
| Python 3.9 | Wrong image. Flash 64-bit Raspberry Pi OS Desktop for Pi 5. |
| `--update` says one-file package | This Pi is running the ARM tarball. Copy a new tarball or reinstall from git (**§3.2**). |
| `--update` / fast-forward failed | Uncommitted edits or a diverged branch. See **§8.1**. Do not merge on the shop floor. |
| `--update` / **UPDATE** pulled but UI unchanged | `sudo systemctl restart fh6parse-kiosk`. Missing sudoers: **§3.2**. |
| Badge is only **v1.4.1** (no `+sha`) **and** no yellow **UPDATE** | Running code cannot see `.git`. One-file tarball, or `pip3 install .` (not `-e`) into site-packages. **UPDATE** compares git SHAs, not the `1.4.1` number. SSH checks and fix below. |
| Badge is **v1.4.1+……** but **UPDATE** still missing | Offline / GitHub blocked (`git fetch` fails), already current, or the panel never slept. Check runs at boot and after screensaver wake. `sudo systemctl restart fh6parse-kiosk` or wait for idle-wake. |
| **UPDATE** says failed / kiosk did not restart | `sudo -n systemctl restart fh6parse-kiosk` from user `kiosk` should succeed after **§3.2**. Then `sudo systemctl restart fh6parse-kiosk`. |
| No **3D cube** next to files | Read the chip next to the cube legend: **searching…** (looking for `.stp`), **rendering…** (drawing a hit — wait), **no STEP** (no matching `.stp` on stick or `model_roots`), **Z: off** (company share not mounted), **no CAD** (`pip3 install -e '.[models]'`). Rev mismatch counts as no STEP. Print still works. |
| Cube shows, ticket has no picture | Status not `device:/dev/usb/lp0` (CUPS intercepted). Printer rejected `GS v 0`. Test text-only first (**§3.5**). |
| Pictures vanished after `--update` | `--update` reinstalls `.[models]` when CAD was already importable. If cubes are still gone, run `sudo pip3 install -e '.[models]' --break-system-packages`. |
| Pictures still shaded / grey mush | Old cache. `rm -rf /tmp/fh6parse-models` and wait for the cube again. The current renderer is black edges on white only. |
| No `WARNING:` for a wrong D | Clone is older than this pull. `git log -1 --oneline` must mention D vs T. D is checked on G43 and on G41/G42. |
| No `WARNING:` after tapping / G95 | Next `Txx M6` (or M30) must still be in G95. A `G94` on the next tool’s line cancels it. |
| No empty-pocket `WARNING:` on an idle T | The **last** Txx M6 with no motion is spindle prep (quiet). Earlier idle Txx M6 should warn. |

**Badge without SHA / no UPDATE.** SSH as `kiosk`:

```
python3 -m fh6parse --version
python3 -c "import fh6parse, sys; print(fh6parse.__file__); print('frozen', getattr(sys, 'frozen', False))"
```

Want `--version` like `1.4.1+0f05f3d` (any 7-char SHA) and `__file__` under `/home/kiosk/fh6parse/`. If `__file__` is in `/usr/local/lib` (or you start a `./fh6parse` one-file binary), this process is not the git checkout — there is no yellow button. Put it on the shop path:

```
cd /home/kiosk/fh6parse
git fetch
git pull --ff-only
sudo pip3 install -e . --break-system-packages
sudo systemctl restart fh6parse-kiosk
```

After that the chip is **v1.4.1+** plus the short git SHA. Later origin commits show **UPDATE** (hash if the number is still 1.4.1). Print still works until you tap it.

CLI without the kiosk (reports next to the NC file):

```
python3 -m fh6parse /path/program.nc
python3 -m fh6parse --format 80mm-load --stdout /path/program.nc
python3 -m fh6parse --format 80mm-set --stdout /path/program.nc
python3 -m fh6parse --format 80mm --stdout /path/program.nc
```

(`80mm-min` is still accepted and prints LOAD. `80mm` is RUN.)

---

## 7. Files on disk

| Path | Role |
| --- | --- |
| `/home/kiosk/fh6parse` | Source checkout (shop update path) |
| `/etc/fh6parse-kiosk.ini` | Pins, printer, idle, `model_roots` (never overwritten by **UPDATE**) |
| `/home/kiosk/.config/fh6parse/ui.ini` | Screen language, mill (including **Add mill…**), GPIO pins, encoder ticks. Written by settings. Survives **UPDATE**. Leftover `width` / `height` from older builds are ignored. |
| `/etc/systemd/system/fh6parse-kiosk.service` | Autostart |
| `/etc/sudoers.d/fh6parse-kiosk` | NOPASSWD restart for on-screen **UPDATE** |
| `packaging/fh6parse-kiosk.ini.example` | Template |
| `packaging/fh6parse-kiosk.service` | Template |
| `/tmp/fh6parse-models` | Cached STEP bitmaps (safe to delete) |

---

## 8. Updating the kiosk

This section is for **fh6parse 1.4.1** on a **git checkout** (`/home/kiosk/fh6parse`). The package number stays **1.4.1** until you tag a newer release; the kiosk chip, office GUI, and `--version` also show the git short SHA (`v1.4.1+abc1234`) so you can see which commit is running. Confirm first:

```
python3 -m fh6parse --version
```

You want `fh6parse 1.4.1+……` (also **v1.4.1+……** on the kiosk). The kiosk **never updates by itself**. Print works with or without a network.

### 8.1 First pull to 1.4.1 (already installed, older number)

If `--version` is older than 1.4.1, SSH as `kiosk`:

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

On each kiosk start, and again when the screensaver wakes (encoder, USB insert, HID, optional spare), a background thread runs `git fetch` (~20 s timeout) and compares `HEAD` to the tracked branch (`@{upstream}`, else `origin/master` / `origin/main`, else `origin/HEAD`). The button appears only when origin can fast-forward this checkout (local is an ancestor of origin). A checkout that is **ahead** of origin (you already pulled 1.4.1, origin still looks like 1.4.0) does **not** show **UPDATE to 1.4.0**. A second fetch is skipped while one is already running, while **UPDATE** is already on screen, or while an install is in progress. **Nothing is installed until you tap the button.**

| After the check | What you see |
| --- | --- |
| Offline, timeout, one-file binary, or already current | No button. **v…** stays at the top. Print as usual. |
| Running from site-packages / tarball (badge has no `+sha`) | No button. **§6** — install `-e` from `/home/kiosk/fh6parse`. |
| Origin has a newer commit | Yellow **UPDATE to x.y.z** (or a short git hash if the number did not change). Status: `v1.4.1 → x.y.z · tap UPDATE to install and restart`. |
| This checkout is already ahead of origin, or the histories diverged | No button. Fast-forward would fail or would go backwards. |

Tap **UPDATE** once (touch or **U**). That is the only action: `git pull --ff-only`, pip only if `pyproject.toml` changed, then **restart** `fh6parse-kiosk`. Print is paused only while that runs. The new version is live after the restart.

`kiosk` cannot restart a system unit unless you installed the sudoers file in **§3.2**. Without it the pull may succeed and the screen stays on the old process — then:

```
sudo systemctl restart fh6parse-kiosk
```

The check also runs after idle wake, so a commit pushed while the panel was black can show **UPDATE** without a reboot. If the kiosk stayed awake the whole time, restart it (or wait until the next power-on / next sleep-wake) before the button can appear.

### 8.3 Keyboard / SSH (`--update`)

Wake the screen if it is black. **Esc** once leaves fullscreen, **Esc** again closes the window if you need a desktop terminal. If systemd owns the display, open a terminal on `:0` or SSH as `kiosk`.

```
python3 -m fh6parse --version
python3 -m fh6parse --update
python3 -m fh6parse --version
```

`--update` and the on-screen button do this, in order:

1. `git pull --ff-only` in the clone (refuses messy merges)
2. `pip3 install -e .` **only if** `pyproject.toml` changed; otherwise skips pip. If STEP cubes already work (`[models]` importable), that pip uses `.[models]` so pictures stay. A kiosk that never had CAD stays `-e .` and does not pull numpy/trimesh. If cubes still vanish, see **§3.7**.
3. `systemctl restart fh6parse-kiosk` if that unit exists; if that fails, `sudo -n systemctl restart fh6parse-kiosk`. Otherwise it prints “restart the kiosk yourself”

It never writes `/etc/fh6parse-kiosk.ini` or `~/.config/fh6parse/ui.ini`. Pins, printer, idle, `model_roots`, and language stay as you set them.

### 8.4 One-file ARM tarball

No **UPDATE** button. `python3 -m fh6parse --update` (or `./fh6parse --update`) exits with a message to copy a new tarball or switch to a git clone. That package is a first copy, not the 1.4.1 upgrade path. To convert: follow **§3.2** (git + pip), point systemd `ExecStart` back to `python3 -m fh6parse --kiosk --config /etc/fh6parse-kiosk.ini`, then **§8.2**.

### 8.5 Office GUI (Windows exe / Linux git)

The office window (`fh6parse.exe`, or `python3 -m fh6parse --gui`) uses the **same one-click UPDATE** as the kiosk: a yellow **UPDATE to x.y.z** (or a git hash) bar under the mill/print row. Nothing is installed until you click it; then the window restarts.

| Install | What the bar checks | What one click does |
| --- | --- | --- |
| Frozen Windows exe | GitHub latest release asset `fh6parse-*-windows-x64.exe` newer than **1.4.1** | Download, swap the exe, restart |
| Git checkout (Windows or Linux) | `git fetch` vs origin, same as **§8.2** | `git pull --ff-only`, pip if `pyproject.toml` changed (keeps `[models]` if CAD is already there), restart the GUI |

The check runs at launch and again when you click back into the window. Offline or already current: no bar. Frozen **1.4.1** PCs only show the bar after you tag a **newer** version (`vX.Y.Z` must match `_version.py`). Git checkouts show a hash while the badge stays **1.4.1**.

---

## 9. Field test

Take this sheet to the Pi. The kiosk must show **v1.4.1** at the top right.

**1. Get this code onto the Pi** (user `kiosk`):

```
cd /home/kiosk/fh6parse
git fetch
git checkout master
git pull --ff-only
git log -1 --oneline
sudo systemctl restart fh6parse-kiosk
```

`git log -1` on current master should mention **mill encoder** / **LOAD** / **SET** (or **G54** / travel if that is an older pull). The on-screen badge is still **v1.4.1**. STEP isometrics, D vs T, USB `/dev/usb/lp0`, cycle time, and kiosk preview are already in older 1.4.1 commits. Or wait for the yellow **UPDATE** after a restart, or after the screen wakes from idle.

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
| RUN ticket status: `device:/dev/usb/lp0` (not `lp:…`) | |
| Ticket text is readable (PC852 Polish comments), then cut | |
| Open cover → status **Pokrywa otwarta**; RUN / LOAD / SET do not print | |
| Paper out → status **Brak papieru**; RUN / LOAD / SET do not print | |
| Cover closed, paper in → LOAD (short), SET (offset/cycle), RUN (full) print and cut | |
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
| Idle Txx M6 (not the last change) → empty-pocket warning | |
| Last Txx M6 with no motion stays quiet (spindle prep) | |
| `T12` then `M6` on the next line counts as one T12 change | |
| `G68` then `G69` → `G68 T… L… to G69 T… L…` on LOAD / SET / RUN | |
| `G68` with no `G69` → `G68 T… L… without G69` | |
| `(…!…)` comments listed as programmer notes | |
| Highlight preview (below the list): ops, cycle time, 3D ready, isometric scaled to the 600×1024 band | |

**4. STEP views** (`.stp` on the USB stick, or `model_roots`; CAD extra required)

| Check | Pass |
| --- | --- |
| Stick has `Program.nc` + matching `.stp` (root or subfolder) | |
| **3D cube** appears when the model is ready (no NAS needed) | |
| Stacked isometric on the kiosk preview / Windows GUI (not paper only) | |
| Two stacked views, part not a flat 45° slab (true isometric) | |
| Black lines on white — no grey shading | |
| Through-holes as ellipses, not filled blobs | |
| Long shaft is a thin strip across 80 mm | |
| Print without a cube is still text-only, no wait | |
| Settings (**F2** / **PL** chip): language + mill / **Add mill…** on the first page; **LOAD / SET / RUN tickets**, **GPIO pins**, **Knobs and print wait** as submenus (scrollbar + Esc back); mill form has tool length, ATC, offset, G53 travel; survives restart | |
| Optional spare GPIO (unwired OK): press sleeps, press wakes; print buttons still ignored while black | |
| Optional J2 power: omit it and USB-C still boots; do not set WAIT_FOR_POWER_BUTTON without J2 | |
| NVMe Base Duo under the Pi, official 512 GB 2230 in slot A: `lsblk` shows `nvme0n1`; git checkout lives on that disk | |
| Panel USB 3.0 (27 mm): stick in the enclosure socket lists `.nc`; P047 still on a separate Pi USB-A | |
| Official Active Cooler on FAN header; GPIO screw terminal on the header **or** a 40-pin riser if it will not fit | |
| USB-C and HDMI0 clamped to the case; no USB-C extension on the 27 W PSU | |
| PETG case, vents above the cooler and below the Duo; PCIe flex not creased | |
| File knob: rest is stable; highlight changes halfway to the next tooth | |
| Mill knob: mill name next to **v…** changes; persists like **Add mill…** | |
| Colour chips on the bottom of the screen: green LOAD, yellow SET, red RUN left→right | |
| LOAD has T / H / D / S / Min Z / load boxes, no STEP / offset / chart | |
| SET has mill, offset, cycle, `!` notes, no share chart / each Txx M6 / M00 | |
| RUN has STEP (when ready), offset, time split (G0/F/ATC), tool list, each change, no load boxes / sign-off | |

Windows office PC: double-click the exe (or `python -m fh6parse --gui` from a git clone). **Polski / English** radios at the top right (default English). Set **STEP folders…**. **Add mill…** next to the mill combo (name, rapids m/min, B/C rapid, tool-change seconds, optional max rpm, optional G53 ATC X/Y/Z, work offset X/Y/Z, travel min/max per axis). Next to the preview, tick which **report sections** to include (file/O, mill, printed-at, header comments, `!` notes, STEP, offset corners, Ømax/Z, cycle, share chart, **time split**, tool list, load boxes, each Txx M6, M00, extra warnings, sign-off). **Use LOAD pack** / **SET** / **RUN** copies a factory pack into those ticks. Preview, Print A4, Print 80 mm, and Save all use the same ticks. There are no LOAD / SET / RUN print buttons on the GUI — those exist only on the kiosk. G68, D vs T, empty pocket, S max, late offset, G95, and travel-too-big always print. Last NC folder, report folder, A4 vs 80 mm, and the section checklist are remembered. If CAM overwrites an open `.nc` (mtime or size), the preview reloads from disk — wait for **Reading…** / **Reloaded …** before print. A wireframe cube means the STEP bitmap is ready; the stacked isometric also appears above the report preview. With mill travel set, the ticket includes the work-offset origin rectangle in G53 mm when that box is ticked. Windows print is still the browser dialog, not `/dev/usb/lp0`. If GitHub (frozen exe) or origin (git) has a newer build, a yellow **UPDATE to …** bar appears under the mill/print row — one click, then the window restarts (same as the kiosk). The check also runs when you click back into the window. Frozen **1.4.1** office boxes only show UPDATE after you tag a **newer** version. Publish by tagging **vX.Y.Z** (GitHub Actions builds it) or `packaging\build_windows.bat` then `packaging\publish_windows.ps1`. The tag must match `_version.py`. Do not overwrite `fh6parse-kiosk.ini` next to the exe.

