# fh6parse kiosk hardware archive

Shop URLs die. This file is the buy list that still works without them: **name, SKU / EAN, size, what it is, how to substitute**. Wiring and pin map stay in [LINUX-KIOSK.md](LINUX-KIOSK.md) and [LINUX-KIOSK-WIRING.pdf](LINUX-KIOSK-WIRING.pdf).

Archived **2026-09-20**. Manufacturer PDFs in [hardware-archive/](hardware-archive/). Wayback: `https://web.archive.org/web/*/THE_URL`.

Do **not** fit the Raspberry Pi M.2 HAT+ from the SSD kit. OS disk is the **Pimoroni Duo + official 512 GB 2230 SSD**. GPIO is the **Kamami screw terminal**, on a **40-pin riser** if the cooler is in the way. Assemble must-dos: **§ Must do** below and [LINUX-KIOSK.md](LINUX-KIOSK.md) **§2.13**.

---

## How to replace a dead listing

1. Match **SKU / EAN / manufacturer part** first.
2. If those are gone, match the **physical facts** in the “Substitute” column (hole size, pin count, voltage).
3. Prefer the **manufacturer** page over a marketplace clone.

---

## Board and storage

| Use | Buy as | IDs that survive | Shop (may die) | Manufacturer / brief | Substitute |
| --- | --- | --- | --- | --- | --- |
| Computer | Raspberry Pi **5**, 64-bit OS | BCM2712, 40-pin GPIO identical to Pi 4 | any Pi 5 | [raspberrypi.com/products/raspberry-pi-5](https://www.raspberrypi.com/products/raspberry-pi-5/) | Pi 5 only (RP1 GPIO). Not Pi 4 for this cooler / PCIe / J2. |
| PSU | Official Raspberry Pi **27 W** USB-C (5.1 V / 5 A) | 27 W, USB-C, 5 A | any official PSU | [raspberrypi.com/products/27w-usb-c-power-supply](https://www.raspberrypi.com/products/27w-usb-c-power-supply/) | Must be 5 A. Phone chargers and Pi 3 2.5 A supplies are not enough. |
| Cooler | Raspberry Pi **Active Cooler** | Botland **RPI-23925**, EAN **5056561803357**. 4-pin FAN, 8000 rpm PWM, spring clips, Pi 5 only | [Botland.store](https://botland.store/raspberry-pi-5-mounting-elements/23925-raspberry-pi-active-cooler-heatsink-fan-for-raspberry-pi-5-5056561803357.html) | [raspberrypi.com/products/active-cooler](https://www.raspberrypi.com/products/active-cooler/) · brief [RP-008188](hardware-archive/RP-008188-DS-raspberry-pi-active-cooler-product-brief.pdf) | Clip-on aluminium + 4-pin blower on the Pi 5 FAN header. Not a Pi 4 fan. |
| NVMe board | Pimoroni **NVMe Base Duo** | **PIM704**, EAN **769894025024**, Botland **PIM-24851**. 87.5 × 56 mm, 2× M.2 M-key 2230–2280, PCIe Gen 2 FPC | [Botland.pl](https://botland.com.pl/rozszerzenia-gpio-i-nakladki-hat-do-raspberry-pi-5/24851-plytka-rozszerzen-nvme-base-duo-do-raspberry-pi-5-pimoroni-pim704-769894025024.html) | [shop.pimoroni.com/products/nvme-base-duo-for-raspberry-pi-5](https://shop.pimoroni.com/products/nvme-base-duo-for-raspberry-pi-5) · [getting started](https://learn.pimoroni.com/article/getting-started-with-nvme-base-duo) | Dual M-key NVMe **under** the Pi 5 on the **PCIe FPC**. Not a 40-pin HAT. Not the official M.2 HAT+. |
| OS disk | Raspberry Pi **SSD 512 GB**, M.2 **2230**, NVMe M-key | From kit Botland **RPI-25484**, EAN **5056561805023**. 22 × 30 × 2.3 mm, 3.3 V, max 2.8 W, TLC, PCIe Gen3 | [SSD Kit 512 GB](https://botland.com.pl/raspberry-pi-hat-nakladki-pci-express/25484-raspberry-pi-ssd-kit-512gb-zestaw-z-dyskiem-ssd-do-raspberry-pi-5-5056561805023.html) — **take the disk only** | [raspberrypi.com/products/ssd](https://www.raspberrypi.com/products/ssd/) · brief [RP-008357](hardware-archive/RP-008357-DS-raspberry-pi-ssd-product-brief.pdf) | Official Pi 512 GB 2230 NVMe. Duo **slot A**, 2230 standoff hole. Kit HAT+ stays in the drawer. |
| Spare PCIe flex (drawer) | Pimoroni **PCIe Pipe** 35 mm or 50 mm | **PIM703** (35 mm) / **PIM702** (50 mm) | Botland / Pimoroni (sold next to the Duo) | Same Duo getting-started | The OS cable. Clips break; keep one spare. |
| Case | 3D-printed enclosure | **PETG** (not PLA). Vents above the cooler and below the Duo | — | — | PLA softens ~60 °C. Cooler brief wants airflow. |

---

## GPIO and panel

| Use | Buy as | IDs that survive | Shop (may die) | Manufacturer / brief | Substitute |
| --- | --- | --- | --- | --- | --- |
| GPIO screws | 40-pin screw-terminal breakout | Kamami **588019**, EAN **5906623475650**. Board ~58 × 22 mm, 40-pin female, screw terminals, M2.5 standoffs, screwdriver | [Kamami](https://kamami.pl/prototypowanie-raspberry-pi/588019-modul-hat-ze-zlaczami-srubowymi-dla-raspberry-pi-5906623475650.html) | Same 40-pin screw block as the old 52Pi / AliExpress listing | 40-pin GPIO screw terminal, silk BCM (`IO17` = GPIO 17). Pin 1 at USB-C. |
| If terminal will not fit | 40-pin **GPIO riser** | Extra-tall **2×20 female-to-male** stacking header | any electronics shop | — | Same pin 1. Do not rotate. Terminal sits on the riser. |
| File + mill knobs | DFRobot Fermion **EC11** | **SEN0235**. 20 pulses/turn, VCC / GND / A / B / C. 3.3–5 V | DFRobot / clones labelled SEN0235 | [wiki.dfrobot.com SEN0235](https://wiki.dfrobot.com/Fermion_EC11_Rotary_Encoder_Module_SKU_SEN0235) | Two modules. Power from **3.3 V** only. Leave shaft **C** open. |
| LOAD / SET / RUN | Three **16 mm** 5-pin vandal, momentary, **5 V** ring LED | LAS16-style. Tabs: LED+ LED− NO C NC. 2.8 mm Faston | Allegro / industrial 16 mm 5 V ring | Meter the tabs — silk varies | Green LOAD, yellow SET, red RUN. NC unused. LED on 5 V, **not** GPIO. |
| Sleep (optional) | Fourth same vandal, or any momentary NO | Same as LOAD | — | — | NO → BCM 25, C → GND. Unwired is fine. |
| Panel power (optional) | Momentary NO on Pi 5 **J2** | Two pads next to RTC, GPIO pin-40 corner. Not a 40-pin GPIO | — | Pi 5 reduced schematic, `PWR_BTN` | Short the two J2 pads. Not BCM 25 / 20. |
| Pendrive socket | Metal **USB 3.0 Type-A** panel mount | **27 mm** round cutout, Type-A female on the front, USB 3 pigtail | [Allegro 17741983408](https://allegro.pl/oferta/gniazdo-usb-3-0-typu-a-metalowe-do-zabudowy-na-pendrive-panelowe-27-mm-17741983408) | Any metal USB 3.0 A 27 mm bulkhead | Pigtail to Pi **USB 3** (blue). P047 stays on **USB 2**. Not GPIO. |
| Printer | MUNBYN **P047** / ITPP047 | 80 mm ESC/POS, USB, auto-cutter, own mains PSU | MUNBYN / ITPP047 | `/dev/usb/lp0`, DLE EOT status | 80 mm thermal with cutter. Do not power from Pi USB. |
| Display | Waveshare **7″ HDMI LCD (C)** | SKU **13857**, native **1024×600**. micro-HDMI on **HDMI0** | Waveshare / resellers | [waveshare.com/7inch-hdmi-lcd-c](https://www.waveshare.com/7inch-hdmi-lcd-c.htm) | 1024×600 landscape. App geometry matches native. Do not rotate unless the panel is physically turned. |
| Keypad (future) | SparkFun Qwiic 12-key | **COM-15290**, I²C 0x4B | SparkFun | Official Qwiic 4-pin on GPIO 2/3 | Leave header 3 / 5 empty until fitted. |

---

## Consumables (no SKU)

| Use | Spec |
| --- | --- |
| GPIO sense (encoder A/B, button NO) | **24 AWG** stranded (0.25 mm²), under ~40 cm |
| 3.3 V, 5 V LED+, GND | **22 AWG** stranded (0.34 mm²) |
| J2 flying leads | 26–28 AWG, under 20 cm |
| Vandal tabs | Insulated **2.8 mm Faston**, crimped |
| Screw ends | Bootlace ferrule, strip ~5 mm |
| Colours | Black GND · orange 3.3 V · red 5 V LED+ only · brown RUN (not red) · green LOAD · yellow SET · violet SLEEP · blue file A/B · white/grey mill A/B |
| USB-C / HDMI strain | Clamp both to the case. No USB-C extension on the 27 W PSU |
| Panel USB hole | Thick boss, metal nut + washer. Pigtail clamped to the case, not the Pi |

---

## Must do (assemble)

These keep the kiosk alive in a mill shop. Same list in [LINUX-KIOSK.md](LINUX-KIOSK.md) **§2.13**.

| # | Do | If you skip it |
| --- | --- | --- |
| 1 | **Never 5 V on a BCM pin.** LED rings on pin 2 only. RUN is **brown**, not red. | Dead Pi |
| 2 | Seat the **PCIe flex** power-off, both clips locked, no crease. The four Duo standoffs carry the sandwich, not the cable. | Black screen, OS gone, SD slot often blocked |
| 3 | **Clamp USB-C and micro-HDMI0** to the case. Official 27 W cable only — **no USB-C extension** (PD 5 A dies). | Undervoltage / blank HDMI after vibration |
| 4 | Screw-terminal silk is **BCM**: `IO17` = GPIO 17, not header pin 17. Pin 1 at USB-C. Do not rotate a riser. | 3.3 V on a GPIO or one-pin-over short |
| 5 | **PETG** case, vents **above** the Active Cooler and **below** the Duo. Do not pack foam on the blower. | Thermal throttle / PLA warp |
| 6 | Strain-relieve the GPIO bundle and the USB 3 pigtail to the **case**, not the Pi header. | Walked screws / cracked USB hole |

---

## Suggestions (shop, first month)

| Do | Why |
| --- | --- |
| Spare PCIe flex (PIM702 / PIM703) in the drawer | Clips are fragile; this is the OS cable |
| Thick boss + nut/washer on the 27 mm USB; dummy plug when idle | Operator yank cracks 3D print; metal dust in the socket |
| Keep the USB 3 pigtail off the encoder loom | USB 3 is noisy; knobs skip |
| Solder or glue the EC11 Dupont end | Pin rows walk; Pi end is already screws |
| Cable-tie a GPIO riser so it cannot lift | Extra connector walks |
| Dab of threadlocker on the 2230 M2; check after a week | Tiny screw, vibration |
| Coarse foam on the cooler intake | CNC dust in the blower |
| Official 27 W brick close to the Pi | Long/cheap USB-C leads drop 5 A |

Leave unless it bites: J2 halt, UPS, slot B clone, PCIe Gen 3, RAID.

---

## Shop URLs (copy for Wayback)

If a shop 404s: open `https://web.archive.org/web/*/URL` with the URL below.

```
https://kamami.pl/prototypowanie-raspberry-pi/588019-modul-hat-ze-zlaczami-srubowymi-dla-raspberry-pi-5906623475650.html
https://botland.com.pl/rozszerzenia-gpio-i-nakladki-hat-do-raspberry-pi-5/24851-plytka-rozszerzen-nvme-base-duo-do-raspberry-pi-5-pimoroni-pim704-769894025024.html
https://botland.com.pl/raspberry-pi-hat-nakladki-pci-express/25484-raspberry-pi-ssd-kit-512gb-zestaw-z-dyskiem-ssd-do-raspberry-pi-5-5056561805023.html
https://botland.store/raspberry-pi-5-mounting-elements/23925-raspberry-pi-active-cooler-heatsink-fan-for-raspberry-pi-5-5056561803357.html
https://allegro.pl/oferta/gniazdo-usb-3-0-typu-a-metalowe-do-zabudowy-na-pendrive-panelowe-27-mm-17741983408
https://shop.pimoroni.com/products/nvme-base-duo-for-raspberry-pi-5
https://learn.pimoroni.com/article/getting-started-with-nvme-base-duo
https://www.raspberrypi.com/products/active-cooler/
https://www.raspberrypi.com/products/ssd/
https://www.waveshare.com/7inch-hdmi-lcd-c.htm
https://wiki.dfrobot.com/Fermion_EC11_Rotary_Encoder_Module_SKU_SEN0235
```

---

## Not in the box (do not buy for this kiosk)

| Part | Why |
| --- | --- |
| Raspberry Pi **M.2 HAT+** (in the SSD kit) | Occupies the 40-pin header. GPIO terminal + cooler lose. Disk moves to the Duo. |
| 52Pi EP-0129 LED GPIO HAT | Too tall vs the Active Cooler. Kamami 588019 is the slim screw block. |
| Analog keypad (e.g. DFR0792) | Pi 5 has no ADC. Future keypad is Qwiic I²C. |
| Pi 3 / 4 PSU, Pi 4 cooler | Wrong current / wrong FAN header. |
| USB-C extension on the 27 W PSU | PD 5 A fails; undervoltage. Clamp the official cable. |
