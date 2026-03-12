# Reference ROMs

Stock / factory EPROM dumps for use as baselines in DigifantTool.

These are 27C256 (32KB) dumps of unmodified factory EPROMs from Digifant 1 ECUs.
Provided for reference, comparison, and verification purposes only.

---

## Included ROMs

| File | Application | Rev Limit | Notes |
|------|-------------|-----------|-------|
| `G60_PG_StockEprom_022B93EE.BIN` | Corrado G60 / Golf G60 / Jetta G60 (PG engine) | ~6201 RPM | Primary G60 reference |
| `G40_StockEprom.BIN` | VW Polo G40 Mk3 | ~6601 RPM | Source: YOU54F/PoloG40Digifant |
| `G40_Mk2_StockEprom.BIN` | VW Polo G40 Mk2 | — | Different ROM layout — map offsets unconfirmed |

---

## Map Layout Compatibility

G60 PG and G40 Mk3 share the same Digifant 1 map structure:

| Map | Address | Size |
|-----|---------|------|
| Ignition 16×16 | `0x4004` | 256 bytes |
| Fuel 16×16 | `0x4104` | 256 bytes |
| RPM Scalar | `0x420C` | 16 × 16-bit |
| Rev Limit (G40 Mk3) | `0x5BC2` | 16-bit word |
| Rev Limit (G60 PG) | `0x4BF2` | 16-bit word |

The G40 Mk2 uses a different ROM structure — offsets not yet confirmed.

---

## Guidelines

- **Only stock / factory ROMs belong here.** No aftermarket tunes, no paid tune files.
- These ROMs are widely circulated in the Digifant community and are provided for
  educational and restoration purposes.
- VW/Bosch factory firmware is copyright Bosch GmbH / Volkswagen AG.
- PRs welcome for other verified stock Digifant 1 variants (Golf G60, Jetta G60, Passat G60, etc.)
