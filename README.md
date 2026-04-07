# DigiTool

ROM editor for Bosch Digifant 1, 2, and 3 ECUs. Covers G60 supercharged engines (Corrado, Golf, Jetta, Passat), G40 Polo, Digifant 2 (2.0 8v and 1.8 8v Golf 2 / Jetta 2), and Digifant 3 (ABF 2.0 16v, ABA 2.0 8v, 9A Corrado).

[![Build](https://github.com/dspl1236/DigiTool/actions/workflows/build.yml/badge.svg)](https://github.com/dspl1236/DigiTool/actions/workflows/build.yml)
[![Download](https://img.shields.io/github/v/release/dspl1236/DigiTool?label=Download&logo=github)](https://github.com/dspl1236/DigiTool/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**[Download DigiTool.exe (Windows)](https://github.com/dspl1236/DigiTool/releases/latest)**

All supported ECUs use the **Hitachi HD6303 CPU** (Motorola 6800 derivative), 27C256 / 27C512 EPROM (32KB / 64KB), and the same ignition formula: `(210 − raw) / 2.86 = °BTDC`.

> **⚠ Work in Progress — Use at Your Own Risk**
>
> This tool is under active development. Features may be incomplete, map
> addresses may be unverified, and patches may not have been tested on all
> hardware variants. **Always read and back up your original ROM before making
> any changes.** Read it twice, compare the files, keep both copies safe.
>
> If you find a bug, incorrect address, or have a ROM dump to contribute,
> please [open an issue](https://github.com/dspl1236/DigiTool/issues).


---

## Supported ECUs

### Digifant 1 — G60

| Variant | Application | ECU PN | Rev Limit Addr |
|---------|-------------|--------|----------------|
| G60 Single-Map | Corrado G60 / Golf G60 / Jetta G60 | 037906023 | 0x4BF2 |
| G60 Single-Map | Passat G60 Syncro | 037906023 | 0x4BF2 |
| G60 Single-Map | Golf G60 Limited (16v, 71 built) | 037906023 | 0x4BF2 |
| G60 Triple-Map | G60 triple-map / Corrado SLS | 037906023 | 0x4456 |

Reset vector `45FD` = single-map G60. Reset vector `4C14` = triple-map G60.

### Digifant 1 — G40

| Variant | Application | ECU PN | Rev Limit Addr |
|---------|-------------|--------|----------------|
| G40 Mk3 | Polo G40 Mk3 | 037906025 | 0x5BC2 |
| G40 Mk2 | Polo G40 Mk2 (early, mirrored ROM) | 037906023 | N/A |

Reset vector `54AA` = G40 Mk3. Reset vector `E000` = G40 Mk2.

### Digifant 2

| Variant | Application | Bosch PN |
|---------|-------------|----------|
| DF2 2E | Golf 2 / Jetta 2 / Scirocco 2.0 8v | 0 261 200 262/263/264 |
| DF2 PF | Golf 2 / Jetta 2 1.8 8v | 0 261 200 169/170 |

No immobilizer. Uses a separate 7-pin Ignition Control Unit (ICU) — coil is NOT driven direct from ECU pin 25 (unlike G60). Map addresses UNCONFIRMED — awaiting ROM collection.

### Digifant 3

| Variant | Application | ECU hardware |
|---------|-------------|-------------|
| DF3 ABF | Golf 3 GTI 2.0 16v | Siemens 5WP4307 |
| DF3 ABA | Golf 3 / Vento 2.0 8v | Bosch / Siemens |
| DF3 9A | Corrado 2.0 16v | Siemens 5WP4/5WP5 |

**Has immobilizer.** CPU confirmed HD6303 (NOT 8051 — earlier documentation was wrong). ROM mapped at CPU 0x8000–0xFFFF. Import Ghidra at base address 0x8000, Language: Motorola 6800.

---

## CPU and ROM Architecture

**CPU: Hitachi HD6303** (all supported variants)
- Motorola 6800 derivative — same instruction set as 6801/6803
- NOP = `0x01`
- Conditional branches: `BEQ` = `0x27`, `BNE` = `0x26`
- **NOT** Intel 8051 — do not use 8051 instructions or NOP=0x00

**ROM layout:**
- Digi 1 / G40 / DF2: 32KB, CPU address space 0x0000–0x7FFF. Reset vector at 0x7FFE.
- DF3 ABF: 32KB, CPU address space **0x8000–0xFFFF**. Reset vector at CPU 0xFFFE (physical 0x7FFE). Physical offset = CPU − 0x8000.
- G40 Mk2: 32KB mirrored (upper half = lower half). Use upper half (0x4000–0x7FFF).
- 27C512 chip reads: 64KB file. DigiTool auto-selects the correct half on open.

---

## Ignition Formula

```
°BTDC = (210 − raw) / 2.86
raw   = round(210 − deg × 2.86)
```

| °BTDC | raw |
|-------|-----|
| 0° TDC | 73 |
| 10° | 101 |
| 20° | 153 (approx) |
| 30° | 124 |
| 35° | 110 |
| 45° | 81 |

---

## Rev Limit Formula

```
RPM = 30,000,000 / uint16_big_endian
uint16 = 30,000,000 / RPM
```

Stored as a 16-bit big-endian value at the variant-specific address (see table above).

---

## MAP Sensor Detection

DigiTool detects MAP sensor range automatically from the firmware opcode:

| Opcode | Meaning | Detected range |
|--------|---------|----------------|
| `CE 00 C8` | `LDX #200` (HD6303) | 200 kPa (stock Bosch) |
| `CE 00 FA` | `LDX #250` (HD6303) | 250 kPa (upgraded sensor) |
| `C1 C8` | `CMPB #200` (fallback, 32KB ROMs) | 200 kPa |
| `C1 FA` | `CMPB #250` (fallback) | 250 kPa |

All known factory ROMs use the 200 kPa sensor. No factory 250 kPa ROM has been identified.

---

## Map Tables — G60 Single-Map / G40 Mk3

Both families share the same firmware layout. 32 map tables total.

| Table | Address | Size | Description |
|-------|---------|------|-------------|
| Ignition | 0x4004 | 16×16 | Main ignition map — `(210−raw)/2.86 = °BTDC` |
| Fuel | 0x4104 | 16×16 | Main fuel map |
| RPM Scalar | 0x420C | 16×1 | 16-bit values |
| Coil Dwell | 0x422C | 16×1 | |
| Knock Multiplier | 0x424C | 16×1 | |
| Knock Retard Rate | 0x425C | 16×1 | |
| Knock Decay Rate | 0x426C | 16×1 | |
| Advance vs ECT | 0x429C | 17×1 | |
| Idle Advance Time | 0x42AD | 16×1 | |
| Idle Ign High Limit | 0x42BD | 16×1 | |
| Idle Ign Low Limit | 0x42CD | 16×1 | |
| Warm Up Enrichment | 0x42DD | 17×1 | Cold-start vs ECT |
| IAT Compensation | 0x42EE | 17×1 | Intake air temp |
| ECT Compensation 1 | 0x42FF | 17×1 | |
| ECT Compensation 2 | 0x4310 | 17×1 | |
| Startup Enrichment | 0x4321 | 17×1 | |
| Battery Compensation | 0x4343 | 17×1 | |
| Injector Lag | 0x4354 | 17×1 | |
| Accel Enrich Min ΔMAP | 0x4365 | 16×1 | |
| Accel Enrich Mult ECT | 0x4375 | 17×1 | |
| Accel Enrich Adder ECT | 0x4386 | 17×1 | |
| Hot Start Enrichment | 0x43C9 | 17×1 | |
| OXS Upswing | 0x441A | 16×4 | Lambda rich→lean response |
| OXS Downswing | 0x445A | 16×1 | Lambda lean→rich response |
| Startup ISV vs ECT | 0x446A | 17×1 | |
| Idle Ignition | 0x447B | 16×1 | |
| Boost Cut (No Knock) | 0x450F | 17×1 | MAP threshold, no knock |
| Boost Cut (Knock) | 0x4520 | 17×1 | MAP threshold, with knock |
| ISV Boost Control | 0x4531 | 16×1 | |
| WOT Enrichment | 0x4541 | 17×1 | |
| CO Adj vs MAP | 0x4562 | 17×1 | |
| WOT Initial Enrichment | 0x4573 | 9×5 | |

**G40 Mk3:** identical map layout and addresses as G60 single-map. Only the rev limit address differs (0x5BC2 vs 0x4BF2).

---

## Map Tables — G60 Triple-Map

Three separate ignition maps (selected by load threshold):

| Table | Address | Size | Description |
|-------|---------|------|-------------|
| Ignition Map 1 (Low Load) | 0x4000 | 16×16 | `(210−raw)/2.86 = °BTDC` |
| Ignition Map 2 (Mid Load) | 0x4100 | 16×16 | |
| Ignition Map 3 (WOT) | 0x4200 | 16×16 | |
| Fuel | 0x4300 | 16×16 | |
| RPM Scalar | 0x4500 | 16×1 | |
| Boost Cut (No Knock) | 0x481C | 16×1 | |
| Boost Cut (Knock) | 0x482D | 17×1 | |
| ISV Boost Control | 0x483E | 16×1 | |
| WOT Fuel | 0x484E | 16×1 | |
| Idle Ignition | 0x485F | 16×1 | |

---

## Map Tables — G40 Mk2

ROM mirrored: 0x4000–0x5FFF == 0x6000–0x7FFF.

| Table | Address | Size |
|-------|---------|------|
| Ignition | 0x50A0 | 16×16 |
| Fuel | 0x51A0 | 16×16 |
| 1D Table A | 0x48C0 | 16×1 |
| 1D Table B | 0x52D2 | 16×1 |
| 1D Table C | 0x53E0 | 12×1 |

---

## Map Tables — Digifant 3 ABF

CPU confirmed HD6303. ROM at CPU 0x8000–0xFFFF. Physical offset = CPU − 0x8000.

| Table | CPU Addr | Physical | Size | Status |
|-------|----------|----------|------|--------|
| Ignition | 0x8117 | 0x0117 | 16×16 | CANDIDATE — single ROM only |
| Fuel | 0x84C0 | 0x04C0 | 16×16 | UNCONFIRMED |
| Warm Up Enrichment | 0x8500 | 0x0500 | 18×1 | UNCONFIRMED |
| Idle Ignition | 0x85C0 | 0x05C0 | 16×1 | UNCONFIRMED |
| Boost Cut (No Knock) | 0x86E4 | 0x06E4 | 17×1 | UNCONFIRMED |
| WOT Enrichment | 0x8750 | 0x0750 | 17×1 | UNCONFIRMED |

**All DF3 addresses are unconfirmed until a second ROM diff is completed.**

---

## Code Patches — G60

| Patch key | Address | Stock bytes | Patch bytes | Effect |
|-----------|---------|-------------|-------------|--------|
| `digilag_lo` | 0x6342 | `01 00` | `00 00` | Remove Digi-Lag at low RPM |
| `digilag_hi` | 0x6347 | `03 00` | `00 00` | Remove Digi-Lag at high RPM |
| `open_loop` | 0x6269 | `BD 6D 07` | `01 01 01` | Open-loop lambda (disable O2S correction) |
| `isv_disable` | 0x6287 | `BD 66 0C` | `01 01 01` | Disable ISV (idle speed valve) |

**Digi-Lag** is a factory throttle-response damping routine. Removing it gives sharper throttle pickup at the cost of potential lean stumble on fast tip-in. The 16v Limited factory ROM has digilag already removed (`0x6342/0x6347` both zeroed).

### G40 SNS Lambda Patches

Reverse-engineered from YOU54F reference files. Injects gate routines into 0x41 fill area:

| Patch key | Address | Stock → Patch | Effect |
|-----------|---------|---------------|--------|
| `sns_idle_lambda_gate` | 0x593C | `BD 59 A7` → `BD 77 50` | Idle lambda via SNS gate |
| `sns_wot_lambda_gate` | 0x646F | `BD 6A 20` → `BD 77 1F` | WOT lambda via SNS gate |
| `sns_lambda_branch` | 0x59E5 | `25 05` → `01 01` | Disable rich-correction branch |
| `sns_lambda_magnitude` | 0x6515 | `03` → `01` | Reduce lambda correction: LDD #3 → #1 |

SNS code is injected at 0x771F–0x775C with embedded copyright string `"copyright 2003 snstuning."`.

---

## Immobilizer Bypass — Digifant 3

Digifant 3 ECUs (ABF, ABA, 9A) contain a hardware immobilizer check. When swapping into a pre-immo car the bypass ROM patch removes the check entirely.

**Mechanism:** A 2-byte conditional branch (`BNE` 0x26 or `BEQ` 0x27) after the immo check subroutine is replaced with `NOP NOP` (0x01 0x01, HD6303).

**Status:** Patch addresses are UNCONFIRMED pending Ghidra disassembly. The Apply button in the Immo tab is locked until a patch entry has `confidence = "CONFIRMED"`.

### Ghidra Workflow (ABF)

1. Import 32KB ROM: Language = Motorola 6800, base address = **0x8000**
2. Auto-analyze
3. Navigate to CPU 0xFFFE → read reset vector (e.g. 0x9200 for 037906024G)
4. Navigate to that address, trace startup to find immo check subroutine
5. Find `BNE` (0x26) or `BEQ` (0x27) after the I/O pin read — it branches to a no-injection path
6. Replace 2 bytes with `01 01` (NOP NOP)
7. Physical address = CPU address − 0x8000
8. Update `PATCH_DB` in `immo_patches.py` with confirmed address and `confidence = "CONFIRMED"`

Once an entry is CONFIRMED, the Immo tab shows a live byte-verification check and unlocks the Apply button.

---

## ROM Detection

DigiTool uses a three-tier detection pipeline:

1. **CRC32 fingerprint** → HIGH confidence. Exact match against `KNOWN_CRCS` table (11 known ROMs).
2. **Reset vector** at 0x7FFE → HIGH confidence. Identifies variant and map family.
3. **Heuristic scoring** → MEDIUM or LOW confidence. Scores based on 0x41 fill density, ignition map byte range, MAP sensor opcode, and rev limit plausibility.

DF2 and DF3 are checked first via `detect_rom_family()` (which checks for the `"DIGIFANT 3"` string and part-number patterns). If neither matches, `detect_rom()` handles Digi 1.

---

## Known ROMs

| CRC32 | Variant | Label | RPM |
|-------|---------|-------|-----|
| 0x8c6fec45 | G60 | Corrado / Golf / Jetta G60 — stock | 6201 |
| 0xb6367c2f | G60 Passat | Passat G60 Syncro — stock | 6250 |
| 0x65550fd6 | G60 16v | Golf G60 Limited (16v, 71 built) | 7000 |
| 0x1b198171 | G60 Triple | G60 Triple-Map — stock | 6250 |
| 0x2cbd1e7a | G60 Triple | Corrado SLS — stock | 7001 |
| 0xb2bec49d | G40 Mk3 | Polo G40 Mk3 — stock | 6601 |
| 0xbf9d8fef | G40 Mk2 | Polo G40 Mk2 — stock | N/A |
| 0x52f186c4 | G60 | Theibach RS G60 — 27C512 chip read | 7133 |
| 0x735d3735 | G60 | SNS Tuning Stage 5 G60 (2002) | 7000 |
| 0xe653d271 | G40 Mk3 | SNS WOT/Idle Lambda + 7812 RPM | 7812 |
| 0xc662e1e9 | G40 Mk3 | 7k Rev Limit | 6995 |
| 0xad0c5304 | G40 Mk3 | Eubel Tuning Gifhorn 1995 (UE001) | 6848 |
| 0x78462536 | DF3 ABF | Golf 3 2.0 16v ABF 037906024G — stock | N/A |

---

## KWPBridge Integration

DigiTool optionally connects to KWPBridge for live ECU data overlay. When connected:

- Overview tab shows a green KWP status banner with the connected ECU part number
- KWPBridge channels logged: RPM, load, coolant temp, lambda, ignition advance, knock retard
- Part number is compared against the loaded ROM — mismatch shown as amber warning

KWPBridge runs as a separate process on the same machine. DigiTool polls every 2 seconds.

---

## File Support

- **32KB `.bin` / `.rom` / `.ori`** — standard 27C256 read
- **64KB `.bin`** — 27C512 read. DigiTool selects the correct half automatically:
  - Halves identical → mirrored chip, use lower half
  - Upper half = 0xFF → lower half is the ROM
  - Lower half = 0xFF → upper half is the ROM  
  - Both have data → pick by reset vector plausibility

- **Save 32KB** — writes working 32KB ROM for programming into a 27C256
- **Save 64KB mirrored** — mirrors 32KB into both halves of a 64KB file for 27C512. Both halves are identical — A15 state is irrelevant, no programmer pin configuration needed.

---

## Version History

| Version | Changes |
|---------|---------|
| v0.7.2 | DF3 ABF CPU confirmed HD6303 (not 8051). Immo patches corrected. |
| v0.7.1 | DF3 ABF first ROM confirmed (CRC 0x78462536). |
| v0.7.0 | DF2 and DF3 detection added. Immo tab added. |
| v0.4.0 | Triple-map support, G40 Mk2 support. |
| v0.3.x | G40 Mk3 SNS patch support. |
| v0.2.x | Full map editor, rev limit spinbox, digilag patches. |
| v0.1.x | Initial release: G60 single-map detection and ignition editor. |

---

## Known Limitations

The following items are known gaps that need community input or further reverse-engineering to resolve. If you can help with any of these, please [open an issue](https://github.com/dspl1236/DigiTool/issues).

### ECU checksum — RESOLVED

**G60 (all variants):** No internal checksum. The region 0x7F00-0x7FFF is 0x41 padding. The ECU does not validate ROM integrity at boot. DigiTool can safely edit without checksum correction.

**G40 (Mk2 and Mk3):** A mod-256 checksum exists at offset 0x7F07. Formula: `(sum(rom[0x0000:0x7F00]) + rom[0x7F07]) % 256 == 0xF8`. DigiTool now automatically recalculates this on every save. The ECU may not enforce this checksum at boot (modified ROMs with incorrect checksums are known to run), but it is corrected for completeness.

Confirmed from binary analysis of stock G40 (0261.200.330) vs 7k rev limit mod, March 2026.

### DF2 / DF3 support — PARTIAL

Detection and basic map definitions exist for DF3 ABF (037906024G). However, map addresses are **unconfirmed** and code patches are incomplete. DF2 (2E, PF) has no profile yet. Both are completely different firmware from DF1 (97% byte difference from G60).

**Current state:**
- DF3 ABF: Detection works, immo patch addresses identified (see below), fuel/ign map addresses need verification
- DF2 (2E/PF): No ROM dumps collected, no profile built

**What's needed:** Additional ROM dumps from DF2 and DF3 variants for map hunting and verification. DF3 ABF fuel/ign map addresses need confirmation via Ghidra disassembly or stock vs tuned ROM diff.

### Immobilizer patches are PROVISIONAL

ABF (037906024G) immo bypass addresses are confirmed by binary analysis — three independent strategies identified (Strategy A at 0x4C1C/0x4C32, Strategy B at 0x2CC8/0x2CD3/0x2CDE, Strategy C at 0x1229). All are PROVISIONAL pending bench test on physical hardware. The Apply button is locked until promoted to CONFIRMED.

ABA/ADY immo patches remain UNCONFIRMED (addr=0x0000 placeholder).

**What's needed:** Bench test of ABF Strategy A patches on a physical ECU to promote to CONFIRMED. ABA/ADY ROM dumps for disassembly.

---

## Data Sources

Map offsets, code-patch locations, and ROM fingerprints derived from:
- Yousaf Nabi (YOU54F): PoloG40Digifant wiki, IDA Pro decompilation, XDF files, stock EPROMs
- Joseph Davis / Chad Robertson (BrendanSmall): G60 XDF authorship
- Marc G60T: triple-map XDF additions
- KDA: Russian Digifant logging protocol
