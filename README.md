# DigiTool

**Digifant 1 ECU ROM Editor** — for VW/Audi G60 and G40 Digifant-1 ECUs (Corrado G60, Polo G40, PG-engine variants)

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20Mac-blue)
![ROM](https://img.shields.io/badge/ROM-27C256%2F27C512-yellow)
![ECU](https://img.shields.io/badge/ECU-Digifant--1%20G60%2FG40-orange)
[![Build Windows EXE](https://github.com/dspl1236/DigiTool/actions/workflows/build.yml/badge.svg)](https://github.com/dspl1236/DigiTool/actions/workflows/build.yml)

## ⬇ Download the Desktop App (Windows)

**→ [Download DigiTool.exe (latest build)](https://github.com/dspl1236/DigiTool/releases/latest)**

No install required. Just download and run.

---

## Features

- 🔥 **Ignition Map** — 16×16 heatmap, click any cell for °BTDC decoded value. Triple-map G60 variants get three separate tabs (Low Load / Mid Load / WOT)
- ⛽ **Fuel Map** — 16×16 heatmap with raw byte inspection
- 🌀 **Boost / ISV** — RPM scalar, boost cut (no-knock + knock), ISV control, startup ISV vs ECT
- 🚀 **WOT & Accel** — WOT enrichment, WOT initial enrichment (9×5), CO adj vs MAP, accel enrich min ΔMAP, mult ECT, adder ECT
- 🔩 **Knock & Dwell** — Coil dwell, knock multiplier, knock retard rate, knock decay rate
- ⏱ **Idle & Ignition** — Advance vs ECT, idle advance time, idle ign high/low limits, idle ignition
- 🌡 **Temperature** — Warmup enrichment, IAT comp, ECT comp ×2, startup enrichment, hot start, battery compensation
- 💧 **Lambda / OXS** — Injector lag, OXS upswing, OXS downswing
- ⊕ **Compare / Diff** — Byte-by-byte diff with map region tagging and delta
- ⚑ **ROM Detection** — Auto-identifies variant, calibration status, MAP sensor range (200 vs 250 kPa)
- ⚑ **Code Patches** — Digilag disable, open loop lambda, ISV disable, SNS lambda gates
- 〒 **Hex View** — Full raw hex with region labels, jump-to-address/region
- ↓ **Rev Limit Editor** — Enter target RPM → calculates bytes → exports modified BIN
- ↓ **27C512 Export** — Mirrors 32 KB ROM to 64 KB for direct 27C512/27SF512 burning

## Supported ECUs

| ECU | Chip | Notes |
|-----|------|-------|
| VW Corrado G60 (PG engine) | 27C256 / 27C512 | Primary target |
| VW Polo G40 Mk3 | 27C256 / 27C512 | Same firmware family |
| VW Golf / Jetta G60 | 27C256 / 27C512 | Compatible |
| VW Passat G60 Syncro | 27C256 / 27C512 | Compatible |
| G60 Triple-Map variants | 27C256 / 27C512 | Corrado SLS, SNS tunes |
| VW Polo G40 Mk2 | 27C256 | Earlier ECU, map offsets differ |

## ROM File Loading

DigiTool accepts any of the following file sizes — it normalizes automatically:

| File size | What it is | What DigiTool does |
|-----------|-----------|-------------------|
| 32 KB (32,768 bytes) | Standard 27C256 dump or half of a 27C512 | Load directly |
| 64 KB — both halves identical | 27C512 mirrored dump | Use lower half |
| 64 KB — upper half all `0xFF` | Programmer wrote ROM to lower half | Use lower half |
| 64 KB — lower half all `0xFF` | Programmer wrote ROM to upper half | Use upper half |
| 64 KB — halves differ | Non-standard 27C512 write | Pick half with known reset vector |
| < 32 KB | Partial dump | Pad to 32 KB with `0xFF`, warn |
| 256 bytes | Single map page | Pad and warn — maps will be incomplete |

If the file is a 64 KB chip read, DigiTool will show a brief message explaining which half it used before loading. The 32 KB ROM that's loaded is what gets edited and saved — the 27C512 export always re-mirrors it back to 64 KB.

## EPROM Burning

**Recommended chip: 27C512** (available cheaply from AliExpress, eBay, etc.)

The Digifant 1 ECU uses only address lines A0–A14 (15 bits = 32 KB). A15 is ignored by the ECU's address decoder, so both halves of a 27C512 are accessible identically. This means:

- A 27C512 with the 32 KB ROM mirrored in both halves works perfectly
- It doesn't matter which half the programmer wrote to
- DigiTool's **Save 27C512 .bin** button produces a ready-to-burn 64 KB image (32 KB × 2)

**Workflow:**
1. Edit your ROM in DigiTool
2. Click **Save 27C512 .bin** → saves a 64 KB mirrored image
3. Open your programmer (TL866, T48, etc.) in **27C512 mode**
4. Write the 64 KB file to the chip
5. Done — both halves are identical, ECU reads either one

27C256 chips work too if you have them — use **Save .bin** (32 KB) and program in 27C256 mode.

## Map Locations (G60 PG / G40 Mk3)

| Map | Address | Size |
|-----|---------|------|
| Ignition | 0x4004 | 16×16 |
| Fuel | 0x4104 | 16×16 |
| RPM Scalar | 0x420C | 16×1 (16-bit) |
| Coil Dwell | 0x422C | 16×1 |
| Knock Retard | 0x425C | 16×1 |
| Warmup Enrichment | 0x42DD | 17×1 |
| IAT Compensation | 0x42EE | 17×1 |
| ECT Compensation 1 | 0x42FF | 17×1 |
| Boost Cut (No Knock) | 0x450F | 17×1 |
| Boost Cut (Knock) | 0x4520 | 17×1 |
| ISV Control | 0x4531 | 16×1 |
| WOT Enrichment | 0x4541 | 17×1 |
| Rev Limit (G60 single) | 0x4BF2 | 16-bit word |
| Rev Limit (G40 Mk3) | 0x5BC2 | 16-bit word |

## Usage

### Desktop App (Windows .exe)
Download from the link above — no install, just run.

### Run from Source
```bash
pip install PyQt5
python -m digitool.main
```

### Build EXE
```bash
pip install pyinstaller
python build.py
```

## G60 Code Patches Detected

| Patch | Address | Stock | Patched |
|-------|---------|-------|---------|
| Digilag (low RPM) | 0x6342 | 01 | 00 |
| Digilag (high RPM) | 0x6347 | 03 | 00 |
| Open Loop Lambda | 0x6269 | BD 6D 07 | 01 01 01 |
| ISV Disable | 0x6287 | BD 66 0C | 01 01 01 |

> **Note:** Digi-Lag is a deliberate VW firmware feature — the ECU stays in closed-loop lambda for a fixed time window at WOT to compensate for carbon canister scavenging pressure changes. On a boosted G60 this causes a lean spike (sometimes 16:1 AFR or worse). The Overview tab includes a one-click **Remove Digi-Lag** button with optional WOT Initial Enrichment compensation.

## Formula Reference

- **Ignition**: `(210 - byte_value) / 2.86 = degrees BTDC`
- **Rev Limit**: `30,000,000 / 16-bit_word = RPM`
- **RPM Scalar**: `15,000,000 / 16-bit_word = RPM`
- **Load**: `0–200 kPa (or 0–250 kPa) divided into 16 equal slices`

## Reference ROMs

Stock EPROM dumps are in [`roms/`](roms/). See [`roms/README.md`](roms/README.md) for details.

Included: G60 PG stock, G60 16v Limited, G40 Mk3 stock, G40 Mk2 stock.

## References

- [PoloG40Digifant Wiki](https://github.com/YOU54F/PoloG40Digifant/wiki) by Yousaf Nabi — Binary decompilation, map locations, XDF files
- [audi90-teensy-ecu](https://github.com/dspl1236/audi90-teensy-ecu) — Related Teensy EPROM emulator project
- [the-corrado.net thread #690](https://www.the-corrado.net/showthread.php?690) — Community Digi-Lag documentation
- [gummel.net](https://gummel.net) — G60 tuning reference

## Development

DigiTool was built by [@dspl1236](https://github.com/dspl1236) with the assistance of [Claude](https://claude.ai) (Anthropic). The reverse engineering, ROM analysis, patch address discovery, and tuning knowledge are the result of collaboration between the developer and Claude across many sessions — analysing real ROM files, cross-referencing community resources, and building the tool iteratively.

If you find it useful, contributions and ROM donations (especially Euro G60 variants, BBM tunes, or 250 kPa sensor ROMs) are welcome.
