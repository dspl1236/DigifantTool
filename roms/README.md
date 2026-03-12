# Reference ROMs

Stock / factory EPROM dumps for use as baselines in DigifantTool.

These are 27C256 (32KB) dumps of unmodified factory EPROMs from Digifant 1 ECUs.
Provided for reference, comparison, and verification purposes only.

---

## Included ROMs

| File | Application | Rev Limit | MAP Sensor | Notes |
|------|-------------|-----------|------------|-------|
| `G60_PG_StockEprom_022B93EE.BIN` | Corrado G60 / Golf G60 / Jetta G60 (PG engine) | ~6201 RPM | 200kPa | Primary G60 reference |
| `G40_StockEprom.BIN` | VW Polo G40 Mk3 | ~6601 RPM | 200kPa | Source: YOU54F/PoloG40Digifant |
| `G40_Mk2_StockEprom.BIN` | VW Polo G40 Mk2 | — | **250kPa** | Different ROM layout — map offsets unconfirmed |

---

## MAP Sensor and Load Axis

The load axis in all maps is derived from the MAP (Manifold Absolute Pressure) sensor.
The 0–5V sensor range is divided into **16 equal slices**.

**200kPa sensor (standard G40 Mk3, G60):**
- Each slice = 200kPa ÷ 16 = **12.5kPa per step**
- Full scale = ~1.0 bar boost

**250kPa sensor (G40 Mk2, some variants):**
- Each slice = 250kPa ÷ 16 = **15.6kPa per step**
- Full scale = ~1.5 bar boost
- The ECU still reads 0–255 on the load axis, but the physical boost value represented
  by each step is higher. All boost-indexed maps (WOT enrichment, boost cut, main fuel)
  must be rescaled when swapping sensor types.

> The G40 Mk2 stock ROM has noticeably different fuel map values (avg ~108 raw vs ~127
> for Mk3 G40 and ~156 for G60 PG), consistent with a different load scaling and
> possibly a different ignition formula. Map offsets for the Mk2 are not yet confirmed.

---

## Map Layout (G60 PG + G40 Mk3 — confirmed matching)

| Map | Address | Size |
|-----|---------|------|
| Ignition 16×16 | `0x4004` | 256 bytes |
| Fuel 16×16 | `0x4104` | 256 bytes |
| RPM Scalar | `0x420C` | 16 × 16-bit |
| Rev Limit (G40 Mk3) | `0x5BC2` | 16-bit word |
| Rev Limit (G60 PG triple-map) | `0x4BF2` | 16-bit word |

---

## Guidelines

- **Only stock / factory ROMs belong here.** No aftermarket tunes, no paid tune files.
- These ROMs are widely circulated in the Digifant community and are provided for
  educational and restoration purposes.
- VW/Bosch factory firmware is copyright Bosch GmbH / Volkswagen AG.
- PRs welcome for other verified stock Digifant 1 variants (Golf G60, Jetta G60, Passat G60, etc.)
