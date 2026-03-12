# Reference ROMs

Stock and known-tune EPROM dumps for use as baselines in DigiTool.

These are 27C256 (32KB) dumps of Digifant 1 ECU EPROMs.
Provided for reference, comparison, and tuning education purposes only.

---

## Stock ROMs

| File | Application | Rev Limit | MAP Sensor | CRC32 |
|------|-------------|-----------|------------|-------|
| `G60_PG_StockEprom_022B93EE.BIN` | Corrado G60 / Golf G60 / Jetta G60 (PG engine) | 6201 RPM | 200 kPa | `0x8c6fec45` |
| `PASSG60.BIN` | Passat G60 Syncro | 6250 RPM | 200 kPa | `0xb6367c2f` |
| `limited_16v_G60.BIN` | G60 16v Limited (1.8 16v supercharged) | 7000 RPM | 200 kPa | `0x65550fd6` |
| `G40_StockEprom.BIN` | VW Polo G40 Mk3 | 6601 RPM | 200 kPa | `0xb2bec49d` |
| `G40_Mk2_StockEprom.BIN` | VW Polo G40 Mk2 | — | unknown | `0xbf9d8fef` |

> **Missing stock ROMs** — PRs welcome for verified dumps of:
> G60 Triple-Map stock (`0x1b198171`), Corrado SLS (`0x2cbd1e7a`)

---

## Known Tune ROMs

Reference tunes from YOU54F's PoloG40Digifant repo — useful for patch detection verification.

| File | Base | Changes | Rev Limit | CRC32 |
|------|------|---------|-----------|-------|
| `G40_StockEprom_with7kRevLimit.BIN` | G40 Mk3 stock | Rev limit only | 6995 RPM | `0xc662e1e9` |
| `G40_StockEprom_withWOTidleLambdaMods.BIN` | G40 Mk3 stock | SNS lambda patches + rev limit | 7812 RPM | `0xe653d271` |
| `G40_EubelTuningInGifhorn1995_MinorFuelTimingChanges_BoostCutRemoval_IdleIgnition.BIN` | G40 Mk3 stock | Ignition advance, boost cut removal, rev limit | 6848 RPM | `0xad0c5304` |


---

## Passat G60 Syncro Analysis (vs Golf/Corrado G60 PG)

The Passat G60 Syncro ROM (`0xb6367c2f`) shares the same G60 single-map firmware base as the
Golf/Corrado ROM (`0x8c6fec45`) but has 181 bytes of differences — all of them meaningful factory
calibration changes for the Syncro application. Same code, different tune. Everything is stock Bosch.

**181 bytes changed — key differences:**

| Region | Changes | Detail |
|--------|---------|--------|
| Ignition Map | 58 cells | Substantial advance across rows 7–13, mid-load cols 0–9. Up to **+12.9°** at row 13 col 1. Some retard at cols 13–14 (high-load knock margin) |
| Fuel Map | 46 cells | Scattered ±1–11 raw adjustments, generally leaner mid-load, richer at some high-load cells |
| Hot Start Enrichment | 13 entries | Reduced at low ECT end, increased mid-range — different warm-up profile |
| OXS / Lambda tables | 13 bytes `0x4417–0x4423` | OXS upswing/downswing curve reshaped (pre-cat lambda tuning) |
| WOT Initial Enrichment | Full reshape | `0x4542–0x454C` significantly richer — Syncro under load needs more fuel |
| Boost cut calibration | 3 entries | Minor threshold adjustments |
| ISV constants `0x6685` | 4 bytes | `0x06` → `0x0C` (doubled) — ISV duty cycle or frequency constants |
| Idle/ISV firmware consts `0x6001` | 3 bytes | Idle target and response constants adjusted for Syncro drivetrain load |
| Rev limit | 1 byte | 6201 → **6250 RPM** (49 RPM higher) |

**Interpretation:** The Syncro carried ~20 kg more weight than the Golf/Corrado plus permanent AWD drivetrain losses. The ignition map is notably more aggressive in the mid-load region, suggesting the Bosch engineers trusted the Syncro's extra mass to act as knock damping under normal driving while needing more advance to recover lost efficiency through the drivetrain. The WOT enrichment is richer to protect the engine at sustained high load (towing, off-camber, full AWD engagement). ISV constants doubled — the Syncro's longer drivetrain creates more mechanical drag at idle that needed more ISV authority to compensate.

---

## SNS Lambda Patch Analysis (G40 Mk3)

The WOT/idle lambda tune contains a classic **SNS Tuning (2003)** multi-patch. SNS injects
two gate routines into the `0x41` fill area at `0x771F–0x775C`, including an embedded
`copyright 2003 snstuning.` string. The firmware is then redirected through these gates.

| Patch | Address | Stock bytes | Patched bytes | Effect |
|-------|---------|------------|---------------|--------|
| Idle lambda gate | `0x593C` | `BD 59 A7` | `BD 77 50` | Redirects idle lambda BSR through SNS gate @ 0x7750 |
| WOT lambda gate | `0x646F` | `BD 6A 20` | `BD 77 1F` | Redirects WOT lambda BSR through SNS gate @ 0x771F |
| Lambda branch disable | `0x59E5` | `25 05` | `01 01` | `BCS $+5` → `NOP NOP` — removes rich-correction conditional |
| Lambda correction magnitude | `0x6515` | `03` | `01` | `LDD #3` → `LDD #1` — reduces correction authority (×2 in ROM) |

The gate routines check if a variable at `$01` exceeds `0x74` (116) — using load/throttle
position as a switch to control lambda behaviour separately at idle vs WOT.

DigiTool detects all four patches and badges them individually in the Code Patches panel.


---

## Eubel Tuning Gifhorn 1995 Analysis (G40 Mk3)

This tune contains a timestamped tuner inscription in the lower-half fill area:
> `von UEBEL TUNING GIFHORN für Ingo Helf DO 30.11.1995 12:13:04 UE001`

**ROM format:** 27C512 (64KB) — the 32KB tune is mirrored across both halves.
Stock G40 ROMs use a 27C256 (32KB) with the lower 16KB as `0x41` fill.
This image has actual data in the lower half (ECU reads upper half `0x4000–0x7FFF`).

**45 bytes changed vs G40 Mk3 stock (upper half):**

| Region | Changes | Detail |
|--------|---------|--------|
| Ignition Map | 11 cells | +3.5–5.2° BTDC advance in rows 11–12 (mid-load/high-load columns 0–5) |
| Fuel Map | 2 cells | −14 to −15 raw at row 12 cols 6–7 (slight lean at mid-high load) |
| Boost Cut (no-knock) | 10 entries | Raised from 176–251 → 235–255. Effectively disabled at high RPM |
| Boost Cut (knock) | 17 entries | Uniform raise: 176 → 190 across all RPM (+9 kPa threshold) |
| Rev Limit | 1 byte | 6601 → 6848 RPM (`0x11C1` → `0x111D`) |
| Checksum | 2 bytes | `0x7F01`/`0x7F07` adjusted to compensate rev limit change |

No lambda patches, no code injection. Pure map and threshold adjustments only.
The boost cut table also extends two entries earlier than our current map definition
(`0x450D–0x450E` were also modified) — suggests the no-knock table may be 19 entries, not 17.

---

## MAP Sensor Detection

DigiTool auto-detects the MAP sensor range from the firmware's ADC scaling constant.

| Opcode | Meaning | Sensor |
|--------|---------|--------|
| `CE 00 C8` | `LDX #200` | 200 kPa (standard stock) |
| `CE 00 FA` | `LDX #250` | 250 kPa (high-boost upgrade) |

Fallback for 32KB ROMs: `C1 C8` / `C1 FA` (`CMPB #200` / `CMPB #250`).

**All ROMs in this repo are 200 kPa.** No factory or confirmed 250 kPa Digifant 1 ROM
has been identified. A 250 kPa tuner ROM will have `CE 00 FA` in firmware and DigiTool
will badge it blue automatically.

| Sensor | Full scale | Per map column (÷16) |
|--------|-----------|----------------------|
| 200 kPa | 200 kPa | 12.5 kPa |
| 250 kPa | 250 kPa | 15.6 kPa |

---

## Map Layout (G60 PG / G40 Mk3 — confirmed matching)

| Map | Address | Size |
|-----|---------|------|
| Ignition 16×16 | `0x4004` | 256 bytes |
| Fuel 16×16 | `0x4104` | 256 bytes |
| RPM Scalar | `0x420C` | 16 × 16-bit |
| Rev Limit (G60 single-map) | `0x4BF2` | 16-bit BE |
| Rev Limit (G40 Mk3) | `0x5BC2` | 16-bit BE |
| Rev Limit (G60 triple-map) | `0x4456` | 16-bit BE |

---

## Guidelines

- **Stock ROMs only** for the stock section. Reference tunes (known, documented) are OK in the tune section.
- No paid tunes, no personal tunes, no proprietary tuner files.
- VW/Bosch factory firmware is copyright Bosch GmbH / Volkswagen AG.
