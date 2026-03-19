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

MECHANISM
=========
ABF (Siemens 5WP4, 8051 CPU):
  The immo check is a subroutine that reads an input pin state and sets
  a flag byte in internal RAM. A conditional jump in the injection main loop
  reads this flag and branches to a no-injection path if the flag is set
  (immo not seen). Bypass = replace the conditional jump with NOP×2 (0x00 0x00)
  so the branch is never taken regardless of immo state.

  This is far simpler than ME7 (no SKC, no EEPROM key learning, no seed/key
  algorithm). The bypass is 2 bytes at one confirmed address.

ABA/ADY (HD6303 if confirmed):
  Same mechanism but different address. The CMPB/BEQ or BSR/BNE pattern
  varies by firmware revision — confirm per ROM before patching.

STATUS
======
v0.7.0: Framework only. Patch addresses UNCONFIRMED — placeholders below.
  Addresses will be populated when ROMs are collected and disassembled.
  Use Ghidra with the 8051 (for ABF) or 6303 (for ABA) plugin to locate the
  startup immo check subroutine and the conditional jump after it.

  For ABF: search for a pattern like JZ/JNZ (0x60/0x70) near the start of
  the main injection loop (called every engine cycle). The immo flag byte
  is typically in internal RAM address 0x20-0x7F.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ImmoPatch:
    """One immobilizer bypass patch for a specific ECU part number / ROM."""
    ecu_pn:      str           # ECU part number (e.g. "1H0906025A")
    rom_crc:     int | None    # CRC32 of the target ROM (None = not yet confirmed)
    patch_addr:  int           # Working-half offset to patch
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
# 8051 opcode reference (for ABF patch finding):
#   JZ  rel   = 0x60  (jump if A==0 — used for "flag is clear" check)
#   JNZ rel   = 0x70  (jump if A!=0 — used for "flag is set" check)
#   NOP       = 0x00  (two NOPs replace the 2-byte conditional jump)
#   LJMP addr = 0x02  (3-byte absolute jump — rare in immo bypass context)
#
# HD6303 opcode reference (for ABA patch finding):
#   BEQ rel   = 0x27  (branch if equal / zero flag set)
#   BNE rel   = 0x26  (branch if not equal)
#   NOP       = 0x01  (HD6303 NOP — same as Digi 1 patch convention)

PATCH_DB: list[ImmoPatch] = [

    # ── ABF 2.0 16v (Siemens 5WP4, 8051) ────────────────────────────────────
    ImmoPatch(
        ecu_pn      = "1H0906025 / 1H0906025A (ABF)",
        rom_crc     = None,
        patch_addr  = 0x0000,   # UNCONFIRMED — placeholder
        original    = bytes([0x70, 0x00]),   # JNZ + offset placeholder
        patched     = bytes([0x00, 0x00]),   # NOP NOP (8051)
        description = "ABF immo bypass — replace JNZ (immo flag check) with NOP×2.",
        confidence  = "UNCONFIRMED",
        notes       = (
            "Address 0x0000 is a placeholder.\n"
            "To find the real address:\n"
            "  1. Open the 32KB ROM in Ghidra with the 8051 plugin.\n"
            "  2. Find the startup routine (follows LJMP from reset at 0x0000).\n"
            "  3. Look for a subroutine that reads an external port/pin into A.\n"
            "  4. Find the JZ or JNZ immediately after that call.\n"
            "  5. Replace with 0x00 0x00 (NOP NOP).\n"
            "  6. Update this entry with the confirmed address and original bytes."
        ),
    ),

    ImmoPatch(
        ecu_pn      = "1H0906025B / 1H0906025C (ABF later revision)",
        rom_crc     = None,
        patch_addr  = 0x0000,
        original    = bytes([0x60, 0x00]),   # JZ + offset placeholder
        patched     = bytes([0x00, 0x00]),
        description = "ABF immo bypass (later revision) — JZ variant.",
        confidence  = "UNCONFIRMED",
        notes       = "Later firmware may use JZ instead of JNZ. Confirm per ROM.",
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
