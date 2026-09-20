# fh6parse kiosk hardware archive

Shop URLs die. This file is the buy list that still works without them: **name, SKU / EAN, size, what it is, how to substitute**. Wiring and pin map stay in [LINUX-KIOSK.md](LINUX-KIOSK.md) and [LINUX-KIOSK-WIRING.pdf](LINUX-KIOSK-WIRING.pdf).

Archived **2026-09-20**. Manufacturer PDFs in [hardware-archive/](hardware-archive/). Wayback: `https://web.archive.org/web/*/THE_URL`.

Do **not** fit the Raspberry Pi M.2 HAT+ from the SSD kit. OS disk is the **Pimoroni Duo + official 512 GB 2230 SSD**. GPIO is the **Kamami screw terminal**, on a **40-pin riser** if the cooler is in the way.

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
| Display | 800×600 LCD, portrait | After rotation framebuffer **600×800**. micro-HDMI on **HDMI0** | — | — | Pi 5 HDMI0 = port next to USB-C. |
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
