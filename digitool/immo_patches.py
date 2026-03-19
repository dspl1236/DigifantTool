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
    ImmoPatch(
        ecu_pn      = "037906024G / 037906024H (ABF Golf 3 GTI)",
        rom_crc     = 0x78462536,   # 037906024G 5WP4307 WINTER DATEN_07
        patch_addr  = 0x0000,   # UNCONFIRMED — placeholder
        original    = bytes([0x26, 0x00]),   # BNE + offset (HD6303)
        patched     = bytes([0x01, 0x01]),   # NOP NOP (HD6303 NOP = 0x01)
        description = "ABF immo bypass — replace BNE (immo flag check) with NOP×2.",
        confidence  = "UNCONFIRMED",
        notes       = (
            "CPU confirmed HD6303 (NOT 8051). NOP = 0x01.\n"
            "ROM mapped at CPU 0x8000–0xFFFF. Physical = CPU − 0x8000.\n"
            "To find the real address:\n"
            "  1. Open 32KB ROM in Ghidra, Language: Motorola 6800, base=0x8000.\n"
            "  2. Navigate to reset vector CPU 0x9200 (phys 0x1200).\n"
            "  3. Find subroutine reading external I/O pin (LDAA ext address).\n"
            "  4. Find BNE (0x26) or BEQ (0x27) after that call — target kills injection.\n"
            "  5. Replace 2 bytes with NOP NOP (0x01 0x01).\n"
            "  6. Bench test. Update rom_crc + patch_addr + original bytes."
        ),
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
