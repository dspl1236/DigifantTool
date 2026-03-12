"""
rom_profiles.py  —  DigiTool  v0.4.0
=====================================
ECU variant detection, ROM fingerprinting, map address tables, and display formulas
for Digifant 1 G60 / G40 ECUs (27C256, 32KB EPROM).

SUPPORTED VARIANTS
==================
G60  Single-Map   Corrado G60 / Golf G60 / Jetta G60         reset=45FD  rev@0x4BF2
G60  Single-Map   Passat G60 Syncro                           reset=45FD  rev@0x4BF2
G60  Single-Map   G60 16v Limited (1.8 16v)                   reset=45FD  rev@0x4BF2
G60  Triple-Map   G60 Three-Map stock                          reset=4C14  rev@0x4456
G60  Triple-Map   Corrado SLS                                  reset=4C14  rev@0x4456
G40  Mk3          Polo G40 Mk3                                reset=54AA  rev@0x5BC2
G40  Mk2          Polo G40 Mk2 (early ECU, mirrored ROM)      reset=E000  rev=unknown

DATA SOURCES
============
Map offsets, code-patch locations, and ROM fingerprints derived from:
  - Yousaf Nabi (YOU54F): PoloG40Digifant wiki, IDA Pro decompilation, XDF files, stock EPROMs
  - Joseph Davis / Chad Robertson (BrendanSmall): G60 XDF authorship
  - Marc G60T: triple-map XDF additions
  - KDA: Russian Digifant logging protocol

MAP FORMULAS
============
Ignition (G60/G40):  display_deg = (210 - raw_byte) / 2.86   °BTDC
                     raw_byte    = round(210 - deg * 2.86)
Rev Limit (16-bit):  rpm = 30_000_000 / uint16_be
                     uint16 = 30_000_000 // rpm
MAP sensor:          All known Digifant 1 ROMs use 200 kPa MAP sensor.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict
import zlib


# ---------------------------------------------------------------------------
# Variant constants
# ---------------------------------------------------------------------------

VARIANT_G60         = "G60"
VARIANT_G60_PASSAT  = "G60_PASSAT"
VARIANT_G60_16V     = "G60_16V"
VARIANT_G60_TRIPLE  = "G60_TRIPLE"
VARIANT_G40         = "G40"
VARIANT_G40_MK2     = "G40_MK2"
VARIANT_UNKNOWN     = "UNKNOWN"

VARIANT_LABELS = {
    VARIANT_G60:        "G60 Corrado / Golf / Jetta",
    VARIANT_G60_PASSAT: "G60 Passat Syncro",
    VARIANT_G60_16V:    "G60 16v Limited",
    VARIANT_G60_TRIPLE: "G60 Triple-Map",
    VARIANT_G40:        "G40 Polo Mk3",
    VARIANT_G40_MK2:    "G40 Polo Mk2",
    VARIANT_UNKNOWN:    "Unknown",
}

MAP_FAMILY_SINGLE = "SINGLE"
MAP_FAMILY_TRIPLE = "TRIPLE"
MAP_FAMILY_MK2    = "MK2"


# ---------------------------------------------------------------------------
# Known ROM CRC32 fingerprints
# ---------------------------------------------------------------------------

KNOWN_CRCS: Dict[int, dict] = {
    0x8c6fec45: dict(
        variant=VARIANT_G60,        label="Corrado / Golf / Jetta G60",
        cal="STOCK",  rev_addr=0x4BF2, family=MAP_FAMILY_SINGLE, rpm_limit=6201,
    ),
    0xb6367c2f: dict(
        variant=VARIANT_G60_PASSAT, label="Passat G60 Syncro",
        cal="STOCK",  rev_addr=0x4BF2, family=MAP_FAMILY_SINGLE, rpm_limit=6250,
    ),
    0x65550fd6: dict(
        variant=VARIANT_G60_16V,    label="G60 16v Limited",
        cal="STOCK",  rev_addr=0x4BF2, family=MAP_FAMILY_SINGLE, rpm_limit=7000,
    ),
    0x1b198171: dict(
        variant=VARIANT_G60_TRIPLE, label="G60 Triple-Map (stock)",
        cal="STOCK",  rev_addr=0x4456, family=MAP_FAMILY_TRIPLE, rpm_limit=6250,
    ),
    0x2cbd1e7a: dict(
        variant=VARIANT_G60_TRIPLE, label="Corrado SLS",
        cal="STOCK",  rev_addr=0x4456, family=MAP_FAMILY_TRIPLE, rpm_limit=7001,
    ),
    0xb2bec49d: dict(
        variant=VARIANT_G40,        label="Polo G40 Mk3 (stock)",
        cal="STOCK",  rev_addr=0x5BC2, family=MAP_FAMILY_SINGLE, rpm_limit=None,
    ),
    0xbf9d8fef: dict(
        variant=VARIANT_G40_MK2,    label="Polo G40 Mk2 (stock)",
        cal="STOCK",  rev_addr=None,  family=MAP_FAMILY_MK2,    rpm_limit=None,
    ),
}

# Reset vector → family mapping (bytes at 0x7FFE–0x7FFF as hex string)
RESET_VECTORS: Dict[str, dict] = {
    "45FD": dict(variant=VARIANT_G60,        family=MAP_FAMILY_SINGLE, rev_addr=0x4BF2),
    "4C14": dict(variant=VARIANT_G60_TRIPLE, family=MAP_FAMILY_TRIPLE, rev_addr=0x4456),
    "54AA": dict(variant=VARIANT_G40,        family=MAP_FAMILY_SINGLE, rev_addr=0x5BC2),
    "E000": dict(variant=VARIANT_G40_MK2,    family=MAP_FAMILY_MK2,    rev_addr=None),
}


# ---------------------------------------------------------------------------
# Map definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MapDef:
    name:        str
    data_addr:   int
    cols:        int
    rows:        int
    description: str = ""
    editable:    bool = True

    @property
    def size(self) -> int:
        return self.cols * self.rows

    @property
    def is_2d(self) -> bool:
        return self.rows > 1


# ── G60 Single-Map / G40 Mk3 layout (shared firmware base, 0x4004 origin) ──
G60_SINGLE_MAPS: List[MapDef] = [
    MapDef("Ignition",              0x4004, 16, 16, "°BTDC: (210-raw)/2.86"),
    MapDef("Fuel",                  0x4104, 16, 16, "Raw fuel map"),
    MapDef("RPM Scalar",            0x420C, 16,  1, "16×1, 16-bit values"),
    MapDef("Coil Dwell",            0x422C, 16,  1),
    MapDef("Knock Multiplier",      0x424C, 16,  1),
    MapDef("Knock Retard Rate",     0x425C, 16,  1),
    MapDef("Knock Decay Rate",      0x426C, 16,  1),
    MapDef("Advance vs ECT",        0x429C, 17,  1),
    MapDef("Idle Advance Time",     0x42AD, 16,  1),
    MapDef("Idle Ign High Limit",   0x42BD, 16,  1),
    MapDef("Idle Ign Low Limit",    0x42CD, 16,  1),
    MapDef("Warm Up Enrichment",    0x42DD, 17,  1),
    MapDef("IAT Compensation",      0x42EE, 17,  1),
    MapDef("ECT Compensation 1",    0x42FF, 17,  1),
    MapDef("ECT Compensation 2",    0x4310, 17,  1),
    MapDef("Startup Enrichment",    0x4321, 17,  1),
    MapDef("Battery Compensation",  0x4343, 17,  1),
    MapDef("Injector Lag",          0x4354, 17,  1),
    MapDef("Accel Enrich Min ΔMAP", 0x4365, 16,  1),
    MapDef("Accel Enrich Mult ECT", 0x4375, 17,  1),
    MapDef("Accel Enrich Adder ECT",0x4386, 17,  1),
    MapDef("Hot Start Enrichment",  0x43C9, 17,  1),
    MapDef("OXS Upswing",           0x441A, 16,  4),
    MapDef("OXS Downswing",         0x445A, 16,  4),
    MapDef("OXS Decay",             0x445A, 16,  1),
    MapDef("Startup ISV vs ECT",    0x446A, 17,  1),
    MapDef("Idle Ignition",         0x447B, 16,  1),
    MapDef("Boost Cut (No Knock)",  0x450F, 17,  1),
    MapDef("Boost Cut (Knock)",     0x4520, 17,  1),
    MapDef("ISV Boost Control",     0x4531, 16,  1),
    MapDef("WOT Enrichment",        0x4541, 17,  1),
    MapDef("CO Adj vs MAP",         0x4562, 17,  1),
    MapDef("WOT Initial Enrichment",0x4573,  9,  5),
]

# G40 Mk3 — same layout as G60 single but different rev limit address
G40_MK3_MAPS = G60_SINGLE_MAPS  # identical map layout

# ── G60 Triple-Map layout (0x4000 origin) ───────────────────────────────────
G60_TRIPLE_MAPS: List[MapDef] = [
    MapDef("Ignition Map 1 (Low Load)",  0x4000, 16, 16, "°BTDC: (210-raw)/2.86"),
    MapDef("Ignition Map 2 (Mid Load)",  0x4100, 16, 16, "°BTDC: (210-raw)/2.86"),
    MapDef("Ignition Map 3 (WOT)",       0x4200, 16, 16, "°BTDC: (210-raw)/2.86"),
    MapDef("Fuel",                        0x4300, 16, 16, "Raw fuel map"),
    MapDef("RPM Scalar",                  0x4500, 16,  1),
    MapDef("Boost Cut (No Knock)",        0x481C, 16,  1),
    MapDef("Boost Cut (Knock)",           0x482D, 17,  1),
    MapDef("ISV Boost Control",           0x483E, 16,  1),
    MapDef("WOT Fuel",                    0x484E, 16,  1),
    MapDef("Idle Ignition",               0x485F, 16,  1),
]

# ── G40 Mk2 layout (addresses confirmed from YOU54F XDF 2014) ───────────────
# ROM mirrored: 0x4000–0x5FFF == 0x6000–0x7FFF
G40_MK2_MAPS: List[MapDef] = [
    MapDef("Ignition",    0x50A0, 16, 16, "Mk2 canonical address"),
    MapDef("Fuel",        0x51A0, 16, 16),
    MapDef("1D Table A",  0x48C0, 16,  1),
    MapDef("1D Table B",  0x52D2, 16,  1),
    MapDef("1D Table C",  0x53E0, 12,  1),
]

FAMILY_MAPS: Dict[str, List[MapDef]] = {
    MAP_FAMILY_SINGLE: G60_SINGLE_MAPS,
    MAP_FAMILY_TRIPLE: G60_TRIPLE_MAPS,
    MAP_FAMILY_MK2:    G40_MK2_MAPS,
}


# ---------------------------------------------------------------------------
# G60 code patch locations (single-map only)
# ---------------------------------------------------------------------------

CODE_PATCHES = {
    "digilag_lo":   dict(addr=0x4433, stock=b'\x01\x00', patch=b'\x00\x00', label="Digilag (low RPM)"),
    "digilag_hi":   dict(addr=0x4435, stock=b'\x03\x00', patch=b'\x00\x00', label="Digilag (high RPM)"),
    "open_loop":    dict(addr=0x6269, stock=b'\xBD\x6D\x07', patch=b'\x01\x01\x01', label="Open Loop Lambda"),
    "isv_disable":  dict(addr=0x6287, stock=b'\xBD\x66\x0C', patch=b'\x01\x01\x01', label="ISV Disable"),
}


# ---------------------------------------------------------------------------
# Display formulas
# ---------------------------------------------------------------------------

def raw_to_ign_deg(raw: int) -> float:
    """Convert raw ignition byte to degrees BTDC."""
    return round((210 - raw) / 2.86, 1)

def ign_deg_to_raw(deg: float) -> int:
    """Convert degrees BTDC to raw ignition byte."""
    return max(0, min(255, round(210 - deg * 2.86)))

def rev_limit_rpm(uint16_be: int) -> int:
    """Convert 16-bit big-endian rev limit value to RPM."""
    if uint16_be == 0:
        return 0
    return round(30_000_000 / uint16_be)

def rpm_to_rev_limit(rpm: int) -> int:
    """Convert RPM to 16-bit big-endian rev limit value."""
    if rpm == 0:
        return 0
    return round(30_000_000 / rpm)


# ---------------------------------------------------------------------------
# Checksum
# ---------------------------------------------------------------------------

CHECKSUM_INFO = {
    MAP_FAMILY_SINGLE: dict(note="G60 single-map / G40 Mk3 — checksum algorithm TBD"),
    MAP_FAMILY_TRIPLE: dict(note="G60 triple-map — checksum algorithm TBD"),
    MAP_FAMILY_MK2:    dict(note="G40 Mk2 — checksum algorithm TBD"),
}

def compute_checksum(rom: bytes) -> int:
    """CRC32 of the full 32KB ROM."""
    return zlib.crc32(rom[:0x8000]) & 0xFFFFFFFF


# ---------------------------------------------------------------------------
# Detection result
# ---------------------------------------------------------------------------

@dataclass
class DetectionResult:
    variant:        str
    family:         str
    label:          str
    confidence:     str          # "HIGH" | "MEDIUM" | "LOW"
    method:         str
    cal:            str = ""
    rev_addr:       Optional[int] = None
    rpm_limit:      Optional[int] = None
    crc32:          int = 0
    warnings:       list = field(default_factory=list)
    map_sensor_kpa: int = 200    # 200 or 250 — detected from firmware constant

    @property
    def is_known_stock(self) -> bool:
        return self.cal == "STOCK"

    @property
    def is_triple(self) -> bool:
        return self.family == MAP_FAMILY_TRIPLE

    @property
    def is_mk2(self) -> bool:
        return self.family == MAP_FAMILY_MK2

    @property
    def maps(self) -> List[MapDef]:
        return FAMILY_MAPS.get(self.family, [])

    def rev_limit_rpm(self, rom: bytes) -> Optional[int]:
        if self.rev_addr is None:
            return self.rpm_limit
        try:
            hi = rom[self.rev_addr]
            lo = rom[self.rev_addr + 1]
            val = (hi << 8) | lo
            return rev_limit_rpm(val)
        except Exception:
            return self.rpm_limit

    def code_flags(self, rom: bytes) -> Dict[str, bool]:
        """Check G60 code patches — returns {key: True=patched, False=stock}."""
        if self.family == MAP_FAMILY_MK2:
            return {}
        flags = {}
        for key, p in CODE_PATCHES.items():
            addr = p["addr"]
            try:
                actual = bytes(rom[addr:addr + len(p["stock"])])
                flags[key] = (actual == p["patch"])
            except Exception:
                flags[key] = False
        return flags


# ---------------------------------------------------------------------------
# MAP sensor range detection
# ---------------------------------------------------------------------------

# The HD6303 firmware contains a 16-bit immediate load of the sensor's full-scale
# ADC value:
#   CE 00 C8  →  LDX #200  →  200 kPa sensor (stock Bosch 0-200 kPa)
#   CE 00 FA  →  LDX #250  →  250 kPa sensor (high-boost upgrade sensor)
#
# This constant appears twice in the firmware (two MAP routines that use it).
# G40 Mk3 stock confirmed 200 kPa at 0x7220/0x722A.
# G60 triple-map tune (read.BIN) confirmed 200 kPa at 0x710B/0x7115.
# A 250 kPa-calibrated ROM will have CE 00 FA at the same relative locations.

_CE00C8 = bytes([0xCE, 0x00, 0xC8])   # LDX #200
_CE00FA = bytes([0xCE, 0x00, 0xFA])   # LDX #250

def detect_map_sensor(rom: bytes) -> tuple[int, str]:
    """
    Return (kpa: int, method: str) — 200 or 250 kPa.

    Searches the ROM for the firmware constant that encodes the MAP sensor's
    full-scale range.  Returns 200 if ambiguous / not found (safe default).
    """
    n200 = sum(1 for i in range(len(rom) - 2)
               if rom[i:i+3] == _CE00C8)
    n250 = sum(1 for i in range(len(rom) - 2)
               if rom[i:i+3] == _CE00FA)

    if n200 > 0 and n250 == 0:
        return 200, f"CE 00 C8 (LDX #200) found ×{n200} — 200 kPa sensor"
    if n250 > 0 and n200 == 0:
        return 250, f"CE 00 FA (LDX #250) found ×{n250} — 250 kPa sensor"
    if n250 > 0 and n200 > 0:
        # Both present — unusual; go with whichever appears more often
        kpa = 250 if n250 >= n200 else 200
        return kpa, f"Ambiguous: CE 00 C8 ×{n200}, CE 00 FA ×{n250} — defaulting to {kpa} kPa"
    # Neither found (e.g. Mk2 or very different firmware)
    return 200, "MAP sensor constant not found — assuming 200 kPa (default)"


# ---------------------------------------------------------------------------
# Main detection function
# ---------------------------------------------------------------------------

def detect_rom(rom_data: bytes) -> DetectionResult:
    """
    Identify a Digifant 1 ROM from raw bytes.

    Priority:
      1. CRC32 match → HIGH confidence
      2. Reset vector match → HIGH confidence
      3. Heuristics → MEDIUM / LOW
    """
    if len(rom_data) < 0x8000:
        rom_data = rom_data + bytes(0x8000 - len(rom_data))

    data = rom_data[:0x8000]
    crc  = zlib.crc32(data) & 0xFFFFFFFF
    sensor_kpa, sensor_method = detect_map_sensor(data)

    # 1. Known CRC
    if crc in KNOWN_CRCS:
        k = KNOWN_CRCS[crc]
        return DetectionResult(
            variant=k["variant"],
            family=k["family"],
            label=k["label"],
            confidence="HIGH",
            method="CRC32 fingerprint",
            cal=k["cal"],
            rev_addr=k["rev_addr"],
            rpm_limit=k.get("rpm_limit"),
            crc32=crc,
            map_sensor_kpa=sensor_kpa,
        )

    # 2. Reset vector
    vec_bytes = data[0x7FFE:0x8000]
    vec_str   = f"{vec_bytes[0]:02X}{vec_bytes[1]:02X}"
    if vec_str in RESET_VECTORS:
        rv = RESET_VECTORS[vec_str]
        return DetectionResult(
            variant=rv["variant"],
            family=rv["family"],
            label=VARIANT_LABELS.get(rv["variant"], rv["variant"]),
            confidence="HIGH",
            method=f"Reset vector {vec_str} @ 0x7FFE",
            cal="TUNED",
            rev_addr=rv["rev_addr"],
            crc32=crc,
            warnings=["ROM not in known-stock library — likely a tune"],
            map_sensor_kpa=sensor_kpa,
        )

    # 3. Unknown
    return DetectionResult(
        variant=VARIANT_UNKNOWN,
        family=MAP_FAMILY_SINGLE,
        label="Unknown ROM",
        confidence="LOW",
        method="No fingerprint matched",
        crc32=crc,
        warnings=[
            "Could not identify ROM variant.",
            f"Reset vector: {vec_str}",
            f"CRC32: {crc:#010x}",
            "Supported ROMs: G60 Corrado/Golf/Jetta/Passat, G60 16v, G60 Triple-Map, G40 Mk3, G40 Mk2",
        ],
        map_sensor_kpa=sensor_kpa,
    )
