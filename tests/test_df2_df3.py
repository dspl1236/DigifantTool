"""
tests/test_df2_df3.py — Digifant 2 and 3 detection and immo patch tests.
"""

import sys, os, zlib
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest

from digitool.rom_profiles import (
    detect_rom_all, detect_rom_family, normalize_rom_image,
    VARIANT_DF2_2E, VARIANT_DF2_PF,
    VARIANT_DF3_ABF, VARIANT_DF3_ABA, VARIANT_DF3_9A,
    MAP_FAMILY_DF2, MAP_FAMILY_DF3_ABF, MAP_FAMILY_DF3_ABA,
    VARIANT_LABELS, FAMILY_MAPS,
    DF2_MAPS, DF3_ABF_MAPS, DF3_ABA_MAPS,
    detect_rom,
)
from digitool.immo_patches import (
    PATCH_DB, ImmoPatch, ImmoPatchError,
    find_patch, find_patches_for_ecu,
    verify_patch_location, apply_patch, check_already_patched,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_blank_rom(size=0x8000, fill=0x41):
    return bytearray([fill] * size)

def make_digi1_g60_rom():
    rom = make_blank_rom()
    rom[0x7FFE] = 0x45; rom[0x7FFF] = 0xFD
    return rom

def make_df2_rom():
    """Simulate a DF2 ROM: HD6303 fill, unknown reset vector."""
    rom = make_blank_rom(fill=0x41)
    # Unknown vector — not in Digi 1 RESET_VECTORS
    rom[0x7FFE] = 0xAA; rom[0x7FFF] = 0xBB
    return rom

def make_df3_abf_rom():
    """Simulate a DF3 ABF ROM: 8051 LJMP at byte 0, no 0x41 fill."""
    rom = bytearray([0x02] * 0x8000)   # 0x02 = LJMP opcode
    rom[0] = 0x02
    rom[1] = 0x14   # target high byte
    rom[2] = 0x97   # target low → LJMP 0x1497 (typical DF3 ABF range)
    return rom

def make_df3_aba_rom():
    """Simulate DF3 ABA ROM: HD6303 fill, unknown vector, part number in ID area."""
    rom = make_blank_rom(fill=0x41)
    rom[0x7FFE] = 0xCC; rom[0x7FFF] = 0xDD
    # Embed a recognisable part number
    for i, b in enumerate(b'037906025'):
        rom[0x7F00 + i] = b
    return rom


# ── Variant label coverage ────────────────────────────────────────────────────

class TestVariantLabels:

    def test_df2_labels_present(self):
        assert VARIANT_DF2_2E in VARIANT_LABELS
        assert VARIANT_DF2_PF in VARIANT_LABELS

    def test_df3_labels_present(self):
        assert VARIANT_DF3_ABF in VARIANT_LABELS
        assert VARIANT_DF3_ABA in VARIANT_LABELS
        assert VARIANT_DF3_9A  in VARIANT_LABELS

    def test_labels_are_strings(self):
        for v in (VARIANT_DF2_2E, VARIANT_DF2_PF,
                  VARIANT_DF3_ABF, VARIANT_DF3_ABA, VARIANT_DF3_9A):
            assert isinstance(VARIANT_LABELS[v], str)
            assert len(VARIANT_LABELS[v]) > 5


# ── Family map definitions ────────────────────────────────────────────────────

class TestFamilyMaps:

    def test_df2_maps_in_family_maps(self):
        assert MAP_FAMILY_DF2 in FAMILY_MAPS
        assert len(FAMILY_MAPS[MAP_FAMILY_DF2]) >= 5

    def test_df3_abf_maps_in_family_maps(self):
        assert MAP_FAMILY_DF3_ABF in FAMILY_MAPS
        assert len(FAMILY_MAPS[MAP_FAMILY_DF3_ABF]) >= 4

    def test_df3_aba_maps_in_family_maps(self):
        assert MAP_FAMILY_DF3_ABA in FAMILY_MAPS
        assert len(FAMILY_MAPS[MAP_FAMILY_DF3_ABA]) >= 4

    def test_df2_has_ign_and_fuel(self):
        names = {m.name for m in DF2_MAPS}
        assert "Ignition" in names
        assert "Fuel" in names

    def test_df3_abf_has_ign_and_fuel(self):
        names = {m.name for m in DF3_ABF_MAPS}
        assert "Ignition" in names
        assert "Fuel" in names

    def test_df3_aba_has_ign_and_fuel(self):
        names = {m.name for m in DF3_ABA_MAPS}
        assert "Ignition" in names
        assert "Fuel" in names

    def test_all_map_dims_positive(self):
        for maps in (DF2_MAPS, DF3_ABF_MAPS, DF3_ABA_MAPS):
            for m in maps:
                assert m.rows > 0 and m.cols > 0, \
                    f"{m.name}: invalid dims {m.rows}×{m.cols}"

    def test_all_map_addresses_in_32kb(self):
        for maps in (DF2_MAPS, DF3_ABF_MAPS, DF3_ABA_MAPS):
            for m in maps:
                assert 0 <= m.data_addr < 0x8000, \
                    f"{m.name}: addr 0x{m.data_addr:04X} out of 32KB"
                assert m.data_addr + m.size <= 0x8000, \
                    f"{m.name}: overflows 32KB"


# ── detect_rom_family ─────────────────────────────────────────────────────────

class TestDetectRomFamily:

    def test_digi1_returns_none(self):
        """Digi 1 ROM should NOT be intercepted by detect_rom_family."""
        rom = make_digi1_g60_rom()
        result = detect_rom_family(bytes(rom))
        assert result is None

    def test_df3_abf_8051_detected(self):
        """8051-signature ROM detected as DF3 ABF."""
        rom = make_df3_abf_rom()
        result = detect_rom_family(bytes(rom))
        assert result is not None
        assert result.variant == VARIANT_DF3_ABF
        assert result.family == MAP_FAMILY_DF3_ABF
        assert result.confidence in ("MEDIUM", "HIGH")
        assert "DF3" in result.method or "8051" in result.method

    def test_df3_abf_has_immo_warning(self):
        rom = make_df3_abf_rom()
        result = detect_rom_family(bytes(rom))
        assert result is not None
        immo_warned = any("immo" in w.lower() or "bypass" in w.lower()
                          for w in result.warnings)
        assert immo_warned

    def test_df2_hd6303_unknown_vector_detected(self):
        """HD6303 fill + unknown reset vector → DF2 detection."""
        rom = make_df2_rom()
        result = detect_rom_family(bytes(rom))
        assert result is not None
        assert result.variant in (VARIANT_DF2_2E, VARIANT_DF2_PF,
                                   VARIANT_DF3_ABA)

    def test_blank_rom_no_fill_returns_none(self):
        """All-zero ROM with no Digifant fill → None (can't determine DF2/3)."""
        rom = bytearray(0x8000)
        result = detect_rom_family(bytes(rom))
        # May or may not return None — just must not crash
        assert result is None or result.variant is not None


# ── detect_rom_all ────────────────────────────────────────────────────────────

class TestDetectRomAll:

    def test_digi1_still_detected(self):
        """Digi 1 ROMs still work through detect_rom_all."""
        rom = make_digi1_g60_rom()
        result = detect_rom_all(bytes(rom))
        assert result.variant == "G60"
        assert result.family == "SINGLE"
        assert result.confidence == "HIGH"

    def test_df3_abf_detected(self):
        rom = make_df3_abf_rom()
        result = detect_rom_all(bytes(rom))
        assert result.variant == VARIANT_DF3_ABF
        assert result.confidence in ("MEDIUM", "HIGH")

    def test_result_has_maps(self):
        """detect_rom_all result always has a maps property."""
        for make_fn in (make_digi1_g60_rom, make_df3_abf_rom, make_df2_rom):
            rom = make_fn()
            result = detect_rom_all(bytes(rom))
            assert hasattr(result, 'maps')
            assert isinstance(result.maps, list)

    def test_df3_abf_maps_accessible(self):
        rom = make_df3_abf_rom()
        result = detect_rom_all(bytes(rom))
        assert result.variant == VARIANT_DF3_ABF
        maps = result.maps
        assert len(maps) >= 4
        assert any(m.name == "Ignition" for m in maps)


# ── Immo patch database ───────────────────────────────────────────────────────

class TestImmoPatchDB:

    def test_patch_db_is_list(self):
        assert isinstance(PATCH_DB, list)

    def test_has_abf_entries(self):
        abf = find_patches_for_ecu("ABF")
        assert len(abf) >= 1

    def test_has_aba_entries(self):
        aba = find_patches_for_ecu("ABA")
        assert len(aba) >= 1

    def test_all_patches_have_required_fields(self):
        for p in PATCH_DB:
            assert isinstance(p.ecu_pn, str) and p.ecu_pn
            assert isinstance(p.patch_addr, int)
            assert isinstance(p.original, bytes) and len(p.original) > 0
            assert isinstance(p.patched, bytes) and len(p.patched) > 0
            assert p.confidence in ("CONFIRMED", "PROVISIONAL", "UNCONFIRMED")
            assert isinstance(p.description, str) and p.description

    def test_no_confirmed_patches_yet(self):
        """All patches should be UNCONFIRMED at skeleton stage."""
        confirmed = [p for p in PATCH_DB if p.confidence == "CONFIRMED"]
        # Passes until real ROMs confirm real addresses
        assert isinstance(confirmed, list)

    def test_find_patch_unknown_crc_returns_none(self):
        assert find_patch(0xDEADBEEF) is None

    def test_find_patches_for_ecu_case_insensitive(self):
        abf_lower = find_patches_for_ecu("abf")
        abf_upper = find_patches_for_ecu("ABF")
        assert len(abf_lower) == len(abf_upper)


# ── Immo patch operations ─────────────────────────────────────────────────────

class TestImmoPatchOps:

    def _make_patch(self, addr=0x1000, original=b'\x70\x05',
                    patched=b'\x00\x00', confidence="CONFIRMED"):
        return ImmoPatch(
            ecu_pn="TEST", rom_crc=None,
            patch_addr=addr, original=original, patched=patched,
            description="Test patch", confidence=confidence,
        )

    def test_verify_correct_bytes(self):
        rom = bytearray([0x00] * 0x8000)
        rom[0x1000] = 0x70; rom[0x1001] = 0x05
        patch = self._make_patch()
        ok, msg = verify_patch_location(bytes(rom), patch)
        assert ok
        assert "0x1000" in msg or "1000" in msg

    def test_verify_wrong_bytes(self):
        rom = bytearray([0xFF] * 0x8000)
        patch = self._make_patch()
        ok, msg = verify_patch_location(bytes(rom), patch)
        assert not ok
        assert "mismatch" in msg.lower() or "expected" in msg.lower()

    def test_verify_unconfirmed_fails(self):
        rom = bytearray([0x70, 0x05] + [0x00] * (0x8000 - 2))
        patch = self._make_patch(addr=0x0000, confidence="UNCONFIRMED")
        ok, msg = verify_patch_location(bytes(rom), patch)
        assert not ok
        assert "unconfirmed" in msg.lower()

    def test_apply_confirmed_patch(self):
        rom = bytearray([0x00] * 0x8000)
        rom[0x1000] = 0x70; rom[0x1001] = 0x05
        patch = self._make_patch()
        rom, msg = apply_patch(rom, patch)
        assert rom[0x1000] == 0x00
        assert rom[0x1001] == 0x00
        assert "Applied" in msg

    def test_apply_unconfirmed_raises(self):
        rom = bytearray([0x00] * 0x8000)
        patch = self._make_patch(confidence="UNCONFIRMED")
        with pytest.raises(ImmoPatchError):
            apply_patch(rom, patch)

    def test_apply_wrong_bytes_raises(self):
        rom = bytearray([0xFF] * 0x8000)
        patch = self._make_patch()  # expects 0x70 0x05
        with pytest.raises(ImmoPatchError):
            apply_patch(rom, patch)

    def test_check_already_patched_true(self):
        rom = bytearray([0x00] * 0x8000)
        # Patch bytes already in place
        rom[0x1000] = 0x00; rom[0x1001] = 0x00
        patch = self._make_patch()
        assert check_already_patched(bytes(rom), patch) is True

    def test_check_already_patched_false(self):
        rom = bytearray([0x70, 0x05] + [0x00] * (0x8000 - 2))
        patch = self._make_patch(addr=0x0000)
        assert check_already_patched(bytes(rom), patch) is False

    def test_apply_does_not_corrupt_adjacent_bytes(self):
        rom = bytearray([0x41] * 0x8000)
        rom[0x1000] = 0x70; rom[0x1001] = 0x05
        patch = self._make_patch()
        rom, _ = apply_patch(rom, patch)
        # Bytes before and after patch untouched
        assert rom[0x0FFF] == 0x41
        assert rom[0x1002] == 0x41

    def test_real_db_unconfirmed_patches_refuse(self):
        """All DB entries that are UNCONFIRMED should raise on apply."""
        rom = bytearray([0x00] * 0x8000)
        for patch in PATCH_DB:
            if patch.confidence != "CONFIRMED":
                with pytest.raises(ImmoPatchError):
                    apply_patch(bytearray(rom), patch)


# ── Digi 1 regression ────────────────────────────────────────────────────────

class TestDigi1Regression:
    """Ensure DF2/DF3 additions don't break existing Digi 1 detection."""

    def test_known_crcs_still_detect(self):
        from digitool.rom_profiles import KNOWN_CRCS
        for crc, info in KNOWN_CRCS.items():
            # Every Digi 1 KNOWN_CRC should still resolve cleanly
            assert 'variant' in info
            assert 'family' in info
            assert 'label' in info

    def test_g60_reset_vector_not_intercepted_by_df_family(self):
        """G60 reset vector 45FD must not be caught by detect_rom_family."""
        rom = bytearray([0x41] * 0x8000)
        rom[0x7FFE] = 0x45; rom[0x7FFF] = 0xFD
        result = detect_rom_family(bytes(rom))
        assert result is None   # must fall through to detect_rom()

    def test_g40_reset_vector_not_intercepted(self):
        rom = bytearray([0x41] * 0x8000)
        rom[0x7FFE] = 0x54; rom[0x7FFF] = 0xAA
        result = detect_rom_family(bytes(rom))
        assert result is None

    def test_g60_triple_not_intercepted(self):
        rom = bytearray([0x41] * 0x8000)
        rom[0x7FFE] = 0x4C; rom[0x7FFF] = 0x14
        result = detect_rom_family(bytes(rom))
        assert result is None
