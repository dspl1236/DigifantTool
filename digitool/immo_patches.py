"""
digitool/immo_patches.py — Digifant 3 immobilizer bypass patch framework.

CONTEXT
=======
Digifant 3 ECUs (ABF 2.0 16v, ABA/ADY 2.0 8v, 9A Corrado 16v) contain a
hardware immobilizer check. At startup the ECU reads a signal from the
instrument cluster's transponder reader ring. If the signal is absent or
incorrect the ECU kills fuel injection — the engine cranks but won't fire.

When swapping a Digifant 3 engine (e.g. ABF Golf 3 GTI) into a pre-immo car
(Golf 2, early Jetta, early Scirocco, pre-immo Corrado) there is no immo
infrastructure to wire in. The ROM patch removes the check entirely.

These ECUs are 30+ years old. The cars they power are enthusiast rebuilds,
swaps, and restorations — not theft targets.

CPU CONFIRMED (binary analysis, March 2025)
===========================================
ABF (Siemens 5WP4 hardware):
  CPU is HD6303 (Motorola 6800 derivative) — NOT 8051 as previously assumed.
  Confirmed from binary analysis of 037906024G (5WP4307): CE 00 C8 opcode
  (LDX #200, HD6303 instruction) present; reset vector at CPU 0xFFFE (not 0x0000).
  ROM mapped at CPU 0x8000–0xFFFF. Physical offset = CPU − 0x8000.
  Import Ghidra at base address 0x8000.

ABA/ADY (HD6303 — same family as Digi 1/2, confirmed for ABF, assumed for ABA):
  Same CPU family. NOP = 0x01. Conditional branches = BEQ (0x27) / BNE (0x26).

MECHANISM
=========
The immo check is a subroutine that reads an input pin state and sets
a flag byte. A conditional branch in the injection main loop reads this flag
and jumps to a no-injection path if the immo signal is absent.
Bypass = replace the conditional branch with NOP×2 (0x01 0x01, HD6303).

This is far simpler than ME7 (no SKC, no EEPROM key learning, no seed/key
algorithm). The bypass is 2 bytes at one confirmed address.

STATUS
======
v0.7.2: CPU confirmed HD6303. Patch addresses UNCONFIRMED — placeholders below.
  Addresses will be populated when ROMs are disassembled in Ghidra.
  See docs/MAP_LOCATIONS.md for the full HD6303 Ghidra workflow.

v0.7.3: ABF patch addresses CONFIRMED by direct binary analysis (March 2026).
  Site 1: file 0x4C1C (CPU 0xCC1C) — BEQ +25 — primary immo gate
  Site 2: file 0x4C32 (CPU 0xCC32) — BNE +3  — secondary immo gate
  Both sites gate entry to subroutine 0xCC3B (immo countdown reader/decrementer).
  Confidence: PROVISIONAL (addresses confirmed by analysis, bench test pending).
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ImmoPatch:
    """One immobilizer bypass patch for a specific ECU part number / ROM."""
    ecu_pn:      str           # ECU part number (e.g. "037906024G")
    rom_crc:     int | None    # CRC32 of the target ROM (None = not yet confirmed)
    patch_addr:  int           # Working-half offset to patch (CPU-space for DF3 ABF)
    original:    bytes         # Expected bytes before patch
    patched:     bytes         # Replacement bytes
    description: str
    confidence:  str           # CONFIRMED | PROVISIONAL | UNCONFIRMED
    notes:       str = ""


# ---------------------------------------------------------------------------
# Patch database
# ---------------------------------------------------------------------------
# Populated as ROMs are collected and disassembled.
#
# HD6303 opcode reference (ABF and ABA):
#   BEQ rel   = 0x27  (branch if equal / zero flag set)
#   BNE rel   = 0x26  (branch if not equal)
#   NOP       = 0x01  (HD6303 NOP — same as Digi 1/2 patch convention)
#   LDAA ext  = 0xB6  (load accumulator from external address — used to read I/O pin)
#   JSR ext   = 0xBD  (call subroutine)
#
# NOTE: Earlier versions of this file referenced 8051 opcodes (JZ=0x60, JNZ=0x70,
# NOP=0x00). Those have been corrected. ABF CPU is confirmed HD6303.

PATCH_DB: list[ImmoPatch] = [

    # ── ABF 2.0 16v (Siemens 5WP4 hardware — CPU confirmed HD6303) ──────────
    # CPU confirmed HD6303 from binary analysis of 037906024G (5WP4307).
    # NOT 8051. NOP = 0x01. Conditional branches = BNE (0x26) / BEQ (0x27).
    # ROM mapped at CPU 0x8000–0xFFFF. Import Ghidra at base address 0x8000.
    #
    # PATCH ADDRESSES CONFIRMED by direct binary analysis (March 2026):
    #   Method: scan BNE/BEQ where fail path leads to rare JSR subroutine.
    #   Subroutine 0xCC3B: F6 01 11 (LDAB 0x0111) — reads immo countdown counter
    #   Two entry points both gate access to the immo check routine.
    #
    # Site 1: CPU 0xCC1C (file 0x4C1C) — BEQ +25
    #   Context: 7D 01 61 27 19 = TST 0x0161, BEQ +0x19 → JSR 0xCC3B
    #   TST 0x0161 checks if immo init has run; BEQ calls immo status checker
    #
    # Site 2: CPU 0xCC32 (file 0x4C32) — BNE +3
    #   Context: 96 C8 84 03 26 03 = LDAA 0xC8, ANDA #3, BNE +3 → JSR 0xCC3B
    #   Tests lower 2 bits of 0xC8; BNE calls immo counter decrement
    #
    # Both sites must be patched (NOP NOP) for a complete bypass.
    # Patch Site 1 (primary gate, recommended first):
    ImmoPatch(
        ecu_pn      = "037906024G / 037906024H (ABF Golf 3 GTI)",
        rom_crc     = 0x78462536,   # 037906024G 5WP4307 WINTER DATEN_07
        patch_addr  = 0x4C1C,       # File offset (CPU 0xCC1C) — CONFIRMED
        original    = bytes([0x27, 0x19]),   # BEQ +25 (HD6303)
        patched     = bytes([0x01, 0x01]),   # NOP NOP (HD6303 NOP = 0x01)
        description = "ABF immo bypass Site 1 — BEQ gate to immo check subroutine. "
                      "Apply both Site 1 and Site 2 for complete bypass.",
        confidence  = "PROVISIONAL",   # addresses confirmed, bench test pending
        notes       = (
            "CPU confirmed HD6303. ROM mapped CPU 0x8000–0xFFFF (file = CPU - 0x8000).\n"
            "Subroutine 0xCC3B: reads immo countdown at RAM 0x0111, decrements on fail.\n"
            "Site 1 (this patch): TST 0x0161, BEQ +25 → calls immo checker if 0x0161 == 0.\n"
            "Site 2 (patch_addr 0x4C32): BNE +3 → second entry to immo checker.\n"
            "Apply BOTH sites. After patching, verify ROM checksum recalculation.\n"
            "PROVISIONAL: addresses confirmed by binary analysis, bench test pending."
        ),
    ),

    # Patch Site 2 (secondary gate, apply together with Site 1):
    ImmoPatch(
        ecu_pn      = "037906024G / 037906024H (ABF Golf 3 GTI) — Site 2",
        rom_crc     = 0x78462536,
        patch_addr  = 0x4C32,       # File offset (CPU 0xCC32) — CONFIRMED
        original    = bytes([0x26, 0x03]),   # BNE +3 (HD6303)
        patched     = bytes([0x01, 0x01]),   # NOP NOP
        description = "ABF immo bypass Site 2 — BNE gate to immo counter decrement. "
                      "Apply together with Site 1 (0x4C1C) for complete bypass.",
        confidence  = "PROVISIONAL",
        notes       = (
            "LDAA 0xC8, ANDA #3, BNE +3 → JSR 0xCC3B (immo counter decrement).\n"
            "Tests lower 2 bits of RAM 0xC8 — set during immo fail path.\n"
            "Without Site 2, immo counter decrements independently and may still cut injection.\n"
            "Apply both sites for a complete bypass."
        ),
    ),

    # ── ABF — Strategy B: Patch the immo FAIL STORE gates (alternative approach) ──
    # Alternative to Strategy A (patching call gates at 0x4C1C/0x4C32).
    # These three BNE instructions gate the STORES of immo fail codes into RAM.
    # Pattern: LDAA #0x35 / JSR 0xE46E (immo check subroutine) / CMPB #0x00 / BNE +2
    # If BNE taken (mismatch): STAA 0x6A/6B/6D → sets kill flag
    # Patching BNE→NOP NOP: always falls through → kill flag never set
    # Three sites cover all three immo challenge bytes (0x35, 0x36, 0x37).
    # Strategy B is more targeted but requires patching 3 sites vs Strategy A's 2.
    # RECOMMENDATION: Use Strategy A (0x4C1C + 0x4C32) for production use.
    # Strategy B confirmed by binary analysis as a valid alternative approach.
    ImmoPatch(
        ecu_pn      = "037906024G (ABF — Strategy B site 1, challenge byte 0x35)",
        rom_crc     = 0x78462536,
        patch_addr  = 0x2CC8,       # File offset (CPU 0xACC8)
        original    = bytes([0x26, 0x02]),   # BNE +2 (HD6303)
        patched     = bytes([0x01, 0x01]),   # NOP NOP
        description = "ABF immo bypass Strategy B — patch fail-store gate for byte 0x35. "
                      "Alternative to Strategy A. Apply all 3 Strategy B sites together.",
        confidence  = "PROVISIONAL",
        notes       = (
            "Context: LDAA #35 / JSR 0xE46E / CMPB #0 / BNE +2 / STAA 0x6A\n"
            "If BNE taken: immo fail code stored to RAM 0x6A (engine kill trigger).\n"
            "NOP NOP prevents the fail store — engine proceeds normally.\n"
            "Must patch all three Strategy B sites (0x2CC8 + 0x2CD3 + 0x2CDE).\n"
            "Prefer Strategy A (0x4C1C + 0x4C32) — fewer patches, earlier in chain."
        ),
    ),
    ImmoPatch(
        ecu_pn      = "037906024G (ABF — Strategy B site 2, challenge byte 0x36)",
        rom_crc     = 0x78462536,
        patch_addr  = 0x2CD3,
        original    = bytes([0x26, 0x02]),
        patched     = bytes([0x01, 0x01]),
        description = "ABF immo bypass Strategy B — patch fail-store gate for byte 0x36.",
        confidence  = "PROVISIONAL",
        notes       = "Context: LDAA #36 / JSR 0xE46E / CMPB #0 / BNE +2 / STAA 0x6B",
    ),
    ImmoPatch(
        ecu_pn      = "037906024G (ABF — Strategy B site 3, challenge byte 0x37)",
        rom_crc     = 0x78462536,
        patch_addr  = 0x2CDE,
        original    = bytes([0x26, 0x02]),
        patched     = bytes([0x01, 0x01]),
        description = "ABF immo bypass Strategy B — patch fail-store gate for byte 0x37.",
        confidence  = "PROVISIONAL",
        notes       = "Context: LDAA #37 / JSR 0xE46E / CMPB #0 / BNE +2 / STAA 0x6D",
    ),

    ImmoPatch(
        ecu_pn      = "1H0906025 / 1H0906025A / 1H0906025B (ABF later variants)",
        rom_crc     = None,
        patch_addr  = 0x0000,
        original    = bytes([0x27, 0x00]),   # BEQ + offset (HD6303)
        patched     = bytes([0x01, 0x01]),   # NOP NOP (HD6303)
        description = "ABF immo bypass (later variant) — BEQ variant.",
        confidence  = "UNCONFIRMED",
        notes       = "Later firmware may use BEQ instead of BNE. Confirm per ROM.",
    ),

    # ── ABA / ADY 2.0 8v (HD6303 presumed) ───────────────────────────────────
    ImmoPatch(
        ecu_pn      = "037906025 / 037906023E (ABA/ADY)",
        rom_crc     = None,
        patch_addr  = 0x0000,
        original    = bytes([0x27, 0x00]),   # BEQ + offset (HD6303)
        patched     = bytes([0x01, 0x01]),   # NOP NOP (HD6303 = 0x01)
        description = "ABA/ADY immo bypass — replace BEQ (immo check branch) with NOP×2.",
        confidence  = "UNCONFIRMED",
        notes       = (
            "Address 0x0000 is a placeholder.\n"
            "ABA CPU is presumed HD6303 (same as Digi 1) — confirm from ROM.\n"
            "If CPU is confirmed HD6303: NOP = 0x01 (same as Digi 1 patches).\n"
            "If CPU is something else: adjust NOP byte accordingly."
        ),
    ),
]


# ---------------------------------------------------------------------------
# Patch operations
# ---------------------------------------------------------------------------

class ImmoPatchError(Exception):
    pass


def find_patch(rom_crc: int) -> ImmoPatch | None:
    """Return matching patch from PATCH_DB by CRC, or None."""
    return next((p for p in PATCH_DB if p.rom_crc == rom_crc), None)


def find_patches_for_ecu(ecu_pn_fragment: str) -> list[ImmoPatch]:
    """Return all patches whose ecu_pn contains the given fragment."""
    frag = ecu_pn_fragment.replace(' ', '').upper()
    return [p for p in PATCH_DB
            if frag in p.ecu_pn.replace(' ', '').upper()]


def verify_patch_location(rom: bytes, patch: ImmoPatch) -> tuple[bool, str]:
    """
    Check that the bytes at patch.patch_addr match patch.original.
    Returns (ok: bool, message: str).
    """
    if patch.patch_addr == 0x0000 and patch.confidence == "UNCONFIRMED":
        return False, "Patch address unconfirmed — do not apply without ROM disassembly."

    addr = patch.patch_addr
    n    = len(patch.original)
    if addr + n > len(rom):
        return False, f"Patch address 0x{addr:04X} out of range (ROM is {len(rom)}B)."

    found = bytes(rom[addr:addr + n])
    if found != patch.original:
        return False, (
            f"Byte mismatch at 0x{addr:04X}: "
            f"expected {patch.original.hex().upper()} "
            f"found {found.hex().upper()}. Wrong ROM revision?"
        )
    return True, f"Verified: expected bytes {patch.original.hex().upper()} present at 0x{addr:04X}."


def apply_patch(rom: bytearray, patch: ImmoPatch) -> tuple[bytearray, str]:
    """
    Apply immo bypass patch to a ROM bytearray.
    Raises ImmoPatchError if patch is not CONFIRMED or bytes don't match.
    """
    if patch.confidence != "CONFIRMED":
        raise ImmoPatchError(
            f"Patch for {patch.ecu_pn} is {patch.confidence}. "
            "Confirm address via disassembly before applying."
        )
    ok, msg = verify_patch_location(bytes(rom), patch)
    if not ok:
        raise ImmoPatchError(msg)

    addr = patch.patch_addr
    for i, byte in enumerate(patch.patched):
        rom[addr + i] = byte

    return rom, (
        f"Applied: {patch.description}  "
        f"[{patch.patched.hex().upper()} @ 0x{addr:04X}]"
    )


def check_already_patched(rom: bytes, patch: ImmoPatch) -> bool:
    """Return True if the ROM already has the patch bytes applied."""
    addr = patch.patch_addr
    n    = len(patch.patched)
    if addr + n > len(rom):
        return False
    return bytes(rom[addr:addr + n]) == patch.patched
