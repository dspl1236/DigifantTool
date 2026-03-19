# Digifant 1 ECU — Map Locations

## G60 PG / G40 Mk3 (PY) — Standard Layout
> Shared layout. G60 ROM: `022B_93EE`. G40 Mk3 ROM: `G40_StockEprom.BIN`.
> Source: YOU54F/PoloG40Digifant (XDF by Joseph Davis / Chad Robertson)

| Map | Address | Size | Notes |
|-----|---------|------|-------|
| Ignition | 0x4004 | 16×16 | Formula: `(210 - byte) / 2.86 = °BTDC` |
| Fuel | 0x4104 | 16×16 | |
| RPM Scalar | 0x420C | 16×1 16-bit | `15,000,000 / 16bit = RPM` |
| Coil Dwell Time | 0x422C | 16×1 | |
| Knock Multiplier | 0x424C | 16×1 | |
| Knock Retard Rate | 0x425C | 16×1 | |
| Knock Decay Rate | 0x426C | 16×1 | |
| UncalledTable1 | 0x427C | 16×1 | Purpose unknown |
| Advance vs Coolant Temp | 0x429C | 17×1 | |
| Min MAP for Knock Retard | 0x428C | 16×1 | |
| Idle Advance Time | 0x42AD | 16×1 | |
| Idle Ignition High Limit | 0x42BD | 16×1 | |
| Idle Ignition Low Limit | 0x42CD | 16×1 | |
| Warm Up Enrichment | 0x42DD | 17×1 | |
| IAT Temperature Compensation | 0x42EE | 17×1 | |
| ECT Temperature Compensation 1 | 0x42FF | 17×1 | |
| ECT Temperature Compensation 2 | 0x4310 | 17×1 | |
| Startup Enrichment | 0x4321 | 17×1 | |
| Startup Enrichment vs ECT | 0x4332 | 17×1 | |
| Battery Compensation | 0x4343 | 17×1 | |
| Injector Lag | 0x4354 | 17×1 | |
| Accel Enrichment Min Delta-MAP | 0x4365 | 16×1 | |
| Accel Enrichment Multiplier vs ECT | 0x4375 | 17×1 | |
| Accel Enrichment Adder vs ECT | 0x4386 | 17×1 | |
| Accel Enrichment Adder vs ECT 2 | 0x4397 | 17×1 | |
| Pressure Raise Enrichment vs ECT | 0x43A8 | 17×1 | |
| IgnitionRelated_1 | 0x43B9 | 16×1 | Purpose TBD |
| Hot Start Enrichment | 0x43C9 | 17×1 | |
| OXS Upswing | 0x43DA | 16×4 | Lambda O2 control |
| OXS Downswing | 0x441A | 16×4 | Lambda O2 control |
| Startup ISV vs ECT | 0x446A | 17×1 | |
| Idle Ignition | 0x447B | 16×1 | |
| Boost Cut (No Knock) | 0x450F | 17×1 | |
| Boost Cut (Knock) | 0x4520 | 17×1 | |
| ISV Boost Control | 0x4531 | 16×1 | |
| WOT Enrichment | 0x4541 | 17×1 | |
| OXS Decay | 0x445A | 16×1 | |
| CO Adj vs MAP | 0x4562 | 17×1 | |
| WOT Initial Enrichment | 0x4573 | 9×5 | |
| **Rev Limit (G40 Mk3)** | **0x5BC2** | 16-bit | `30,000,000 / 16bit = RPM` |
| **Rev Limit (G60 PG)** | **0x4BF2** | 16-bit | G60 triple-map firmware |

### G60 Code Patches

| Patch | Address | Stock | Patched |
|-------|---------|-------|---------|
| Digilag disable (low RPM) | 0x4433 | `01 00` | `00 00` |
| Digilag disable (high RPM) | 0x4435 | `03 00` | `00 00` |
| Open loop lambda | 0x6269 | `BD 6D 07` | `01 01 01` |
| ISV disable | 0x6287 | `BD 66 0C` | `01 01 01` |

---

## G40 Mk2 — Different ROM Layout
> Source: YOU54F/PoloG40Digifant (`G40_Mk2_StockEprom.xdf`, authored 2014)
> ROM structure: 0x0000–0x3FFF = 0xFF fill. Code occupies 0x4000–0x7FFF.
> **The ROM is mirrored** — 0x4000–0x5FFF mirrors 0x6000–0x7FFF exactly.
> Canonical (non-mirrored) map addresses are in the 0x4000–0x5FFF range.

| # | Address | Size | Notes |
|---|---------|------|-------|
| 3 | 0x50A0 | 16×16 | **Ignition map** (avg 22.4° BTDC — plausible) |
| 4 | 0x51A0 | 16×16 | **Fuel map** (avg ~95 raw) |
| 5 | 0x48C0 | 16×1 | 1D table (corrections/scalar) |
| 6 | 0x52D2 | 16×1 | 1D table |
| 7 | 0x53E0 | 12×1 | 1D table (smaller — 12 bins) |

Mirror addresses (identical content, use canonical above):

| Mirror | Canonical |
|--------|-----------|
| 0x70A0 | 0x50A0 |
| 0x71A0 | 0x51A0 |
| 0x72D2 | 0x52D2 |
| 0x73E0 | 0x53E0 |

Rev limit: Not at 0x5BC2 (reads 0xFFFF on Mk2). Likely encoded differently — scan pending.

---

## Reset Vectors (ROM fingerprinting)

| Vector @0x7FFE | Variant |
|----------------|---------|
| `45 FD` | G60 PG triple-map |
| `54 AA` | G40 Mk3 (PY) |
| `E0 00` | G40 Mk2 |

---

## G60 Firmware Families

Two completely separate firmware families exist for G60 ECUs.

### Family A — Single-Map (reset vector `45FD`, revAddr `0x4BF2`)
> Shared base with G40 Mk3. Same ign/fuel offsets as G40.
> ROMs: 022B_93EE (Corrado/Golf/Jetta), PASSG60 (Passat Syncro), limited_16v

| Map | Address | Size | Notes |
|-----|---------|------|-------|
| Ignition | 0x4004 | 16×16 | `(210 - byte) / 2.86 = °BTDC` |
| Fuel | 0x4104 | 16×16 | |
| RPM Scalar | 0x420C | 16×1 16-bit | |
| Rev Limit | 0x4BF2 | 16-bit | `30,000,000 / 16bit = RPM` |
| (all G40 1D tables) | same as G40 | — | Shared firmware base |

**limited_16v_G60:** Same layout, 7000 RPM rev limit (vs 6201 stock), modified ignition.
Not 250kPa — fuel avg 159.8 is identical range to standard 200kPa G60.
1.8 16v G60 with higher rev ceiling, not a sensor change.

### Family B — Triple-Map (reset vector `4C14`, revAddr `0x4456`)
> Source: YOU54F XDF by Joseph Davis / Chad Robertson / Marc G60T
> ROMs: `Stock G60 Three ignition maps.bin`, `corradoSLS.BIN`

| Map | Address | Size | Notes |
|-----|---------|------|-------|
| Ignition Map 1 | 0x4000 | 16×16 | Low load / light throttle |
| Ignition Map 2 | 0x4100 | 16×16 | Mid load |
| Ignition Map 3 | 0x4200 | 16×16 | High load / WOT |
| Fuel | 0x4300 | 16×16 | |
| RPM Scalar | 0x4500 | 16×1 | |
| Coil Dwell | 0x4520 | 16×1 | |
| Maximum Advance | 0x4530 | 16×1 | |
| Knock Multiplier | 0x4540 | 16×1 | |
| Advance vs ECT | 0x4587 | 16×1 | |
| Idle Advance Time | 0x4598 | 16×1 | |
| Idle Ign High Limit | 0x45A8 | 16×1 | |
| Idle Ign Low Limit | 0x45B8 | 16×1 | |
| Warmup Enrichment | 0x45C8 | 16×1 | |
| IAT Compensation | 0x45DA | 16×1 | |
| ECT Compensation 1 | 0x45EA | 16×1 | |
| Startup Enrichment | 0x460B | 16×1 | |
| Battery Compensation | 0x462E | 16×1 | |
| Accel Enrich Min ΔMAP | 0x463F | 16×1 | |
| Accel Enrich Mult vs ECT | 0x464F | 16×1 | |
| Accel Enrich Adder vs ECT | 0x4660 | 16×1 | |
| OXS Upswing | 0x4692 | 16×4 | Lambda |
| Knock Retard Rate | 0x46A2 | 16×1 | |
| Knock Decay Rate | 0x46B2 | 16×1 | |
| OXS Downswing | 0x46D2 | 16×4 | Lambda |
| OXS Decay Interval | 0x4712 | 16×1 | |
| Startup ISV vs ECT | 0x4722 | 16×1 | |
| Idle RPM Scalar | 0x4733 | 16×1 | |
| Boost Cut (No Knock) | 0x481C | 16×1 | |
| Boost Cut (Knock) | 0x482D | 17×1 | |
| ISV Boost Control | 0x483E | 16×1 | |
| WOT Fuel | 0x484E | 16×1 | |
| Idle Ignition | 0x485F | 16×1 | |
| CO Adjust vs MAP | 0x486F | 16×1 | |
| WOT Initial Enrichment | 0x4880 | 9×5 | |
| Ignition vs IAT | 0x48AD | 16×1 | |
| **Rev Limit** | **0x4456** | 16-bit | `30,000,000 / 16bit = RPM` |


---

# Digifant System Architecture Notes
*Source: VW Pro Training Manual Part 2 (Digifant I and II)*

## ECU Architecture

| Feature | Digifant I (California) | Digifant I (G60 label) | Digifant II |
|---------|------------------------|----------------------|-------------|
| Connector | 38-pin | 25-pin (DF II pinout) | 25-pin ECU + 7-pin ign ctrl |
| Ignition stage | Integrated in ECU | External coil to pin 25 | Separate ignition control unit |
| Lambda control | ECU-integrated | ECU-integrated | ECU-integrated |
| EGR | Yes (CA only) | No | No |
| Fault memory | Yes (CA only) | No | No |

**Note:** The G60 (Corrado/Golf G60) uses the DF II 25-pin connector layout but is
marketed as "Digifant I". It has a CO potentiometer instead of a MAF sensor and adds
boost enrichment. It is NOT the California emissions Digifant I.

## Ignition Map Structure — CONFIRMED (p.16 of manual)

> *"stored in the ignition map in the control unit's memory as **256 single operational
> points, 16 fixed points for each engine load point and 16 for each RPM point**"*

This confirms: **16×16 = 256 cells** — same as DigiTool's existing implementation.
X-axis: 16 RPM points. Y-axis: 16 load points (from airflow sensor potentiometer).

## Base Timing Specification (p.54)

For timing verification / calibration baseline on Digifant II:
- ECT sensor **disconnected**
- Engine speed: **2300 ±50 RPM**
- Checking: **4°–8° BTDC**
- Adjusting to: **6° ±1° BTDC**

This is the reference point for ignition map calibration — with ECT disconnected the
ECU uses a fixed timing value, bypassing coolant temp correction.

## Fuel System Specs

| Parameter | Value |
|-----------|-------|
| Fuel pressure (idle) | 2.5 bar |
| Fuel pressure (load) | 3.0 bar |
| Injection mode | Batch-fire (all injectors simultaneously) |
| Decel fuel cut-off | 2200–2700 RPM (cuts), 1300–1800 RPM (restores) |
| Over-rev fuel cut | 6500 RPM |
| Full throttle enrichment | Activates ~10° before WOT (full throttle switch) |

## Knock Sensor Behaviour

- Per-cylinder retard: up to **15°** maximum retard per cylinder
- Recovery: **3° advance steps** after knock clears
- Test procedure: timing must advance **30° ±3°** at 2300 RPM with ECT disconnected
  when knock sensor is stimulated (brief >3000 RPM blip stores knock info in ECU)
- Torque: 15–26 Nm (11–18 ft-lbs)

## ISV (Idle Stabilizer Valve)

- Normal idle current: **~400 mA**
- Operating range: **380–1000 mA**
- Increases for: cold start, P/S at lock, A/T in gear, electrical loads, A/C on

## OBD Fault Codes (California Digifant I Only)

| Code | Component |
|------|-----------|
| 2112 | Knock sensor / wiring |
| 2232 | Air flow sensor / wiring |
| 2312 | Coolant temperature sensor / wiring |
| 2322 | Intake air temperature sensor / wiring |
| 2342 | Oxygen sensor / wiring |
| 4444 | No faults stored |
| 0000 | End of diagnosis sequence |

---

# Digifant 2 — Map Locations

> **STATUS: UNCONFIRMED** — all addresses are placeholders estimated from community posts
> and similarity to Digi 1 layout. DO NOT tune from these addresses until confirmed
> against a real chip read. Submit ROMs to help confirm.

Engines covered: **2E** (2.0 8v Golf 2 / Jetta 2 / Scirocco), **PF/RV** (1.8 8v Golf 2)
CPU: HD6303 (same family as Digi 1)
ROM: 27C256 (32KB)
Ignition formula: `(210 - raw) / 2.86 = °BTDC` (assumed same as Digi 1 — UNCONFIRMED)

| Map | Address | Size | Notes |
|-----|---------|------|-------|
| Ignition | 0x4004 | 16×16 | Formula unconfirmed. ADDRESSES UNCONFIRMED. |
| Fuel | 0x4104 | 16×16 | ADDRESSES UNCONFIRMED. |
| Warm Up Enrichment | 0x42DD | 17×1 | UNCONFIRMED. |
| Boost Cut (No Knock) | 0x450F | 17×1 | UNCONFIRMED. |
| Boost Cut (Knock) | 0x4520 | 17×1 | UNCONFIRMED. |
| WOT Enrichment | 0x4541 | 17×1 | UNCONFIRMED. |

---

# Digifant 3 — Map Locations

> **STATUS: UNCONFIRMED** — all addresses are placeholders. DO NOT tune from these.

## ABF 2.0 16v (Siemens 5WP4)

CPU: Siemens SAB80C535 (Intel 8051 derivative — **different from HD6303**)
ROM: 27C256 (32KB) or 27C512 (64KB doubled)
Detection: `rom[0] == 0x02` (8051 LJMP opcode at reset vector) + no 0x41 fill
Has immobilizer — see immo_patches.py for bypass framework.
Ignition formula: **UNCONFIRMED** — 8051 encoding likely differs from HD6303's `(210-raw)/2.86`

| Map | Address | Size | Notes |
|-----|---------|------|-------|
| Ignition | 0x5C00 | 16×16 | Formula UNCONFIRMED. Address UNCONFIRMED. |
| Fuel | 0x6C00 | 16×16 | UNCONFIRMED. |
| Warm Up Enrichment | 0x4500 | 17×1 | UNCONFIRMED. |
| Boost Cut (No Knock) | 0x4600 | 17×1 | UNCONFIRMED. |
| Idle Ignition | 0x4700 | 16×1 | UNCONFIRMED. |

## ABA / ADY 2.0 8v

CPU: Presumed HD6303 (same as Digi 1/2) — UNCONFIRMED
Has immobilizer.

| Map | Address | Size | Notes |
|-----|---------|------|-------|
| Ignition | 0x5800 | 16×16 | UNCONFIRMED. |
| Fuel | 0x6800 | 16×16 | UNCONFIRMED. |
| Idle Ignition | 0x447B | 16×1 | UNCONFIRMED. |

## Immobilizer Bypass (Digi 3)

See `digitool/immo_patches.py` for the full framework.

Context: ABF into Golf 2 / early Jetta swaps require bypassing the immo check
because there is no instrument cluster transponder ring to wire in.
The bypass is 2 bytes (NOP×2 replacing a conditional jump after the immo pin check).
All patch addresses are UNCONFIRMED — addresses will be added when ROMs are disassembled.

How to find the patch address (for ABF, 8051 CPU):
1. Open 32KB ROM in Ghidra with 8051 plugin
2. Follow LJMP from reset vector (rom[0:3])
3. Find subroutine that reads an external input pin into accumulator A
4. The conditional jump (JZ 0x60 or JNZ 0x70) after that call is the immo check
5. Replace with NOP NOP (0x00 0x00) — test on bench before driving

---

# ECU Hardware Reference (from xjamiex A2Resource + VW training material)

## Digifant Naming — Important Distinction

The name "Digifant I" is used inconsistently across sources:

| System | Connector | Market | Engines | ICU |
|--------|-----------|--------|---------|-----|
| **Digifant II** (what we call DF2) | 25-pin | Worldwide | 2E 2.0 8v, PF/RV 1.8 8v | Separate 7-pin ICU |
| **Digifant I G60** (what DigiTool covers as Digi 1) | 25-pin | Worldwide | G60, G40 | Integrated coil stage |
| **Digifant I California** | 38-pin | USA only | 2E (California spec) | Integrated coil stage |

The G60 Corrado ECU uses the **same 25-pin connector as Digifant II** and is
often called "Digifant I G60" by parts suppliers but is architecturally the same
family as what DigiTool currently supports. The California 38-pin "Digifant I" is
a distinct, more advanced system with individual injector control and TPS.

## Digifant II — ECU Pin Functions (25-pin)

| Pin | Function | Notes |
|-----|----------|-------|
| 1 | Starter Power | |
| 2 | Oxygen Sensor | |
| 3 | Fuel Pump | |
| 4 | Knock Sensor Signal | |
| 5 | Knock Sensor Ground | |
| 6 | Ground for sensors | |
| 7 | Knock Sensor shield | |
| 8 | Distributor Pin 3 (positive) | |
| 9 | Intake Air Temperature Sensor | |
| 10 | Coolant Temperature Sensor | |
| 11 | Idle/WOT Switch | Binary only — no TPS |
| 12 | Injector Power | All 4 injectors in parallel |
| 13 | Ground | |
| 14 | Power from CU relay | |
| 16 | A/C compressor signal | |
| 17 | Airflow Sensor Potentiometer | MAF — unlike G60 CO pot |
| 18 | Distributor Pin 2 (hall sender) | |
| 19 | Ground | |
| 20 | Malfunction Light | |
| 21 | Airflow Sensor Potentiometer | MAF (second wire) |
| 22 | Idle Stabilizer Valve | |
| 23 | Idle Stabilizer Valve | |
| **25** | **To Ignition Control Unit** | **KEY: Separate ICU required** |

## Digifant II — Ignition Control Unit (7-pin, separate module)

| Pin | Function |
|-----|----------|
| 1 | Coil Pin 1 |
| 2 | Ground |
| 4 | Start/Run power |
| 6 | From Digifant ECU (timing signal) |

The ICU is **not programmable** — it just receives the timing signal from the ECU
and drives the coil. The timing map lives entirely in the ECU ROM. DigiTool edits
the ECU ROM; the ICU requires no modification for tuning.

## G60 / G40 ECU vs Digifant II — Hardware Differences

| Feature | Digifant II (2E/PF) | G60/G40 (DigiTool) |
|---------|--------------------|--------------------|
| Load sensing | MAF sensor (airflow pot, pins 17+21) | CO potentiometer (pin 5) |
| Ignition | Separate 7-pin ICU | Integrated coil power stage |
| Throttle | Binary idle/WOT switch only | Binary idle/WOT switch |
| Injectors | Batch-fired, parallel | Batch-fired, parallel |
| Knock | Single knock sensor | Single knock sensor |
| Connector | 25-pin | 25-pin (same!) |

Because the MAF replaces the CO pot, the load axis interpretation in the fuel map
differs between DF2 and G60. G60 maps are calibrated for CO pot voltage; DF2 maps
are calibrated for MAF airflow voltage. The map structure (16×16) is the same but
the axis scaling is different.
