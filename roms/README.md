# Reference ROMs

Stock and known-tune EPROM dumps for use as baselines in DigiTool.

These are 27C256/27C512 (32KB) dumps of Digifant 1 ECU EPROMs.
Provided for reference, comparison, and tuning education purposes only.

---

## Archival Notice

Several tune files in this repo originate from commercial tuners — specifically **SNS Tuning** (active ~2000–2005, website defunct) and **Eubel Tuning Gifhorn** (1995). These files are preserved here for the following reasons:

- The original sources no longer exist and the files are otherwise lost to time
- They are the primary test cases for DigiTool's patch detection system — without them, the tool's variant-aware flag detection cannot be verified
- They represent unique calibration strategies (injected gate routines, 27C512 format, boost cut removal) that don't appear in any stock ROM
- No commercial interest is being harmed — both tuning operations are defunct and these calibrations have not been sold or distributed commercially for 20+ years

These files are shared in the spirit of technical preservation and education, not redistribution of commercial work. The tuner names and any embedded copyright strings are documented transparently in the analysis sections below. If you are a rights holder and object to inclusion, please open an issue.

VW/Bosch factory firmware is copyright Bosch GmbH / Volkswagen AG.

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
> G60 Triple-Map stock (`0x1b198171`)

---

## Known Tune ROMs

### G60 Single-Map Tunes

| File | Base | Tuner | Changes | Rev Limit | CRC32 |
|------|------|-------|---------|-----------|-------|
| `corradoSLS.BIN` | G60 Triple-Map | Unknown | Rev limit only (stock cal otherwise) | 7001 RPM | `0x2cbd1e7a` |
| `Theibach_RS_G60_mit_27c512_gelesen.bin` | G60 single-map | Unknown (hex editor) | Ignition +5–12° across full map, fuel/IAT/OXS trim, rev limit | 7133 RPM | `0x52f186c4` |
| `STAGE_5_G60.BIN` | G60 single-map | **SNS Tuning 2002** | Heavy tune: fuel rescale, boost raised, WOT enrich, firmware rewrites + injected code | 7000 RPM | `0x735d3735` |

### G40 Mk3 Tunes

| File | Base | Tuner | Changes | Rev Limit | CRC32 |
|------|------|-------|---------|-----------|-------|
| `G40_StockEprom_with7kRevLimit.BIN` | G40 Mk3 stock | Unknown | Rev limit only | 6995 RPM | `0xc662e1e9` |
| `G40_StockEprom_withWOTidleLambdaMods.BIN` | G40 Mk3 stock | **SNS Tuning 2003** | Lambda patches (WOT + idle gates injected into fill area) + rev limit | 7812 RPM | `0xe653d271` |
| `G40_EubelTuningInGifhorn1995_MinorFuelTimingChanges_BoostCutRemoval_IdleIgnition.BIN` | G40 Mk3 stock | **Eubel Tuning Gifhorn** | Ignition advance, boost cut removal, rev limit | 6848 RPM | `0xad0c5304` |


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

## Theibach RS G60 Analysis (vs Golf/Corrado G60 PG)

File name indicates it was read from a 27C512 chip (`mit_27c512_gelesen` = "read with 27C512").
No tuner string found in the fill area — likely edited with a hex editor directly.
**398 bytes changed vs Golf G60 stock.**

| Region | Changes | Detail |
|--------|---------|--------|
| Ignition Map | 180 cells | Uniform +5–6° advance at low/mid load rows 0–6; rising to +10–12° at high-load rows 10–15. Classic full-map timing advance tune |
| Fuel Map | 124 cells | Leaner mid-range rows 9–12 (-7 to -9 raw avg); richer low-load rows 2–7 (+3 to +15) |
| IAT Compensation | 16 entries | Trimmed down — slightly less fuel pullback under charge air heat |
| Warm-up Enrichment | 2 bytes | Reduced at top two ECT entries (-4 raw) |
| ECT Compensation 1 | 2 bytes | Reduced at first two entries (-7 raw) |
| Hot Start Enrichment | 2 bytes | Reduced (less post-hot-start enrichment) |
| OXS Upswing | 6 bytes | Lambda curve reshaped — upswing response slightly faster in upper rows |
| Rev Limit | 2 bytes | 6201 → **7133 RPM** |
| Firmware | 64 bytes | Scattered 1–4 byte constant tweaks: ISV thresholds, lambda scalars — no injected code |

---

## SNS Tuning Stage 5 G60 Analysis (2002)

SNS Tuning copyright string confirmed in fill area at `0x56F0`: `"Copyright (C) 2002 SNStuning.com"`.
Same tuner as the G40 SNS lambda tune (2003). **3065 bytes changed vs Golf G60 stock.**

| Region | Changes | Detail |
|--------|---------|--------|
| Ignition Map | 188 cells | Modest overall advance (+1–2° avg) across full map — conservative given "Stage 5" marketing |
| Fuel Map | 215 cells | Large lean at rows 3–7 mid-load (-16 to -28 raw avg); richer rows 9–11 high load (+5). Pattern consistent with injector rescaling for larger injectors |
| Injector Lag | 2 bytes | +22 raw at upper two ECT entries — larger injectors need longer lag compensation |
| Boost Cut (no-knock) | 14 bytes | Raised 30–42 kPa → 50–75 kPa — significantly more boost permitted before fuel cut |
| Boost Cut (knock) | 10 bytes | Raised 130–150 kPa → 145–170 kPa — cut threshold raised under knock conditions too |
| WOT Enrichment | 15 bytes | Heavily increased all columns: 24–42 raw → 42–58 raw |
| CO Adj vs MAP | 13 bytes | Fully remapped; rich bias active at low/mid MAP (AFR tuning at cruise) |
| OXS Downswing | 6 bytes | Significantly slowed (-16 to -69 raw) — slower lean correction after rich event |
| Idle Ign High Limit | 3 bytes | Upper entries raised +13–28 raw — wider ignition authority at idle |
| RPM Scalar entry 0 | 1 byte | 10201 → 10501 RPM (axis stretch for extended powerband) |
| Startup ISV vs ECT | 9 bytes | ISV duty vs coolant temp reshaped |
| Firmware (code) | 2524 bytes | Large rewrites at `0x4E41–0x547D` and `0x5E00–0x6006`; scattered single-byte calibration constants throughout |
| SNS injected code | ~80 bytes | Routines injected into fill area at `0x56F0–0x5740`, `0x5800–0x5810`, `0x5820–0x5839`, `0x5840–0x5852`, `0x5860–0x5872`, `0x5880–0x588F` |
| Checksum area | 17 bytes | `0x7FA0–0x7FBF` → all `0xFF` (erased/unused, not a calibration checksum region) |
| Rev Limit | 2 bytes | 6201 → **7000 RPM** |

---



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
