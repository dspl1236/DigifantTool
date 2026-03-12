# DigiTool

**Digifant 1 ECU ROM Editor** — for VW/Audi G60 and G40 Digifant-1 ECUs (Corrado G60, Polo G40, PG-engine variants)

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20Mac-blue)
![ROM](https://img.shields.io/badge/ROM-27C256%2032KB-yellow)
![ECU](https://img.shields.io/badge/ECU-Digifant--1%20G60%2FG40-orange)

## Features

- 🔥 **Ignition Map** — 16×16 heatmap, click any cell for °BTDC decoded value
- ⛽ **Fuel Map** — 16×16 heatmap with raw byte inspection
- 🌀 **Boost & ISV** — Boost cut (no-knock + knock), ISV control, WOT enrichment
- ⚙ **Corrections** — Warmup, ECT, IAT, knock retard, coil dwell, accel enrichment
- ⊕ **ROM Compare/Diff** — Byte-by-byte diff with map region tagging and delta
- ⚑ **G60 Code Flags** — Auto-detects Digilag disable, Open Loop Lambda, ISV disable patches
- 〒 **Hex View** — Full raw hex with region labels, jump-to-address/region
- ↓ **Rev Limit Editor** — Enter target RPM → calculates bytes → exports modified BIN

## Supported ECUs

| ECU | Chip | Notes |
|-----|------|-------|
| VW Corrado G60 (PG engine) | 27C256 (32KB) | Primary target |
| VW Polo G40 | 27C256 (32KB) | Same firmware family |
| VW Golf/Jetta G60 | 27C256 (32KB) | Compatible |

## Map Locations (G60 PG)

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
| Rev Limit | 0x5BC2 | 16-bit word |

## Usage

### Web Version
Open `app/DigiTool.html` in any modern browser. No install required.

### Desktop App (Windows .exe)
Download the latest release from the [Releases](../../releases) page.

## Building the Desktop App

```bash
pip install pyinstaller
cd desktop
python build.py
```

## G60 Code Patches Detected

| Patch | Address | Stock | Patched |
|-------|---------|-------|---------|
| Digilag Disable | 0x4433/0x4435 | 01 00 / 03 00 | 00 00 / 00 00 |
| Open Loop Lambda | 0x6269 | BD 6D 07 | 01 01 01 |
| ISV Disable | 0x6287 | BD 66 0C | 01 01 01 |

## Formula Reference

- **Ignition**: `(210 - byte_value) / 2.86 = degrees BTDC`
- **Rev Limit**: `30,000,000 / 16-bit_word = RPM`
- **RPM Scalar**: `15,000,000 / 16-bit_word = RPM`
- **Load**: `0–200 kPa divided into 16 equal slices`

## References

- [PoloG40Digifant Wiki](https://github.com/YOU54F/PoloG40Digifant/wiki) — Binary decompilation & map locations
- Hardware: MC68HC11A1 + MC68HC25 (Motorola) with 27C256 EPROM

## Disclaimer

This tool modifies engine management data. Always keep a backup of your original ROM.
Use at your own risk. Not for road use where prohibited.

## License

MIT
