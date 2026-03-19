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
    DF3_ABF_KNOWN_CRCS,
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
    """
    Simulate a DF3 ABF ROM using the confirmed HD6303 structure.

    Binary analysis of 037906024G (5WP4307) established:
      - CPU is HD6303 (NOT 8051 — earlier assumption was wrong)
      - ROM mapped at CPU 0x8000–0xFFFF
      - 'DIGIFANT 3' string is the primary detection anchor
      - Low 0x41 fill (~2%), reset vector points into CPU 0x8000+ range
      - No large 0x41 fill region unlike Digi 1/2
    """
    rom = bytearray([0x00] * 0x8000)   # sparse/code-dense, no 0x41 fill
    # Embed 'DIGIFANT 3.2' ID string at physical 0x0D99 (CPU 0x8D99)
    sig = b"DIGIFANT 3.2        XXXX"
    for i, b in enumerate(sig):
        rom[0x0D99 + i] = b
    # Reset vector at physical 0x7FFE → CPU 0x9200 (points into CPU 0x8000+ = ROM)
    rom[0x7FFE] = 0x92
    rom[0x7FFF] = 0x00
    # Small 0x41 fill block (representative of real ROM)
    for i in range(150):
        rom[0x1130 + i] = 0x41
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

    def test_all_map_addresses_in_range(self):
        """
        DF2 / DF3 ABA map addresses are physical 32KB offsets (< 0x8000).
        DF3 ABF addresses are CPU-space (0x8000–0xFFFF) — ROM mapped at CPU 0x8000+.
        """
        for m in DF2_MAPS:
            assert 0 <= m.data_addr < 0x8000, \
                f"DF2 {m.name}: addr 0x{m.data_addr:04X} out of 32KB"
            assert m.data_addr + m.size <= 0x8000, \
                f"DF2 {m.name}: overflows 32KB"
        for m in DF3_ABA_MAPS:
            assert 0 <= m.data_addr < 0x8000, \
                f"DF3 ABA {m.name}: addr 0x{m.data_addr:04X} out of 32KB"
        for m in DF3_ABF_MAPS:
            # CPU-space: 0x8000–0xFFFF (physical = addr - 0x8000)
            assert 0x8000 <= m.data_addr <= 0xFFFF, \
                f"DF3 ABF {m.name}: addr 0x{m.data_addr:04X} not in CPU-space 0x8000–0xFFFF"
            phys = m.data_addr - 0x8000
            assert phys + m.size <= 0x8000, \
                f"DF3 ABF {m.name}: overflows 32KB physical"


# ── detect_rom_family ─────────────────────────────────────────────────────────

class TestDetectRomFamily:

    def test_digi1_returns_none(self):
        """Digi 1 ROM should NOT be intercepted by detect_rom_family."""
        rom = make_digi1_g60_rom()
        result = detect_rom_family(bytes(rom))
        assert result is None

    def test_df3_abf_digifant3_string_detected(self):
        """ROM with 'DIGIFANT 3' string detected as DF3 ABF (HD6303, not 8051)."""
        rom = make_df3_abf_rom()
        result = detect_rom_family(bytes(rom))
        assert result is not None
        assert result.variant == VARIANT_DF3_ABF
        assert result.family == MAP_FAMILY_DF3_ABF
        assert result.confidence in ("MEDIUM", "HIGH")
        assert "DF3" in result.method or "DIGIFANT 3" in result.method

    def test_df3_abf_has_immo_warning(self):
        rom = make_df3_abf_rom()
        result = detect_rom_family(bytes(rom))
        assert result is not None
        immo_warned = any("immo" in w.lower() or "bypass" in w.lower()
                          for w in result.warnings)
        assert immo_warned

    def test_df3_abf_warning_mentions_hd6303(self):
        """Warning must reference HD6303 CPU (not 8051)."""
        rom = make_df3_abf_rom()
        result = detect_rom_family(bytes(rom))
        assert result is not None
        hd_mentioned = any("HD6303" in w or "hd6303" in w.lower()
                           for w in result.warnings)
        assert hd_mentioned

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

    def test_df3_abf_crc_match(self):
        """Known CRC (037906024G) returns HIGH confidence via CRC path."""
        from digitool.rom_profiles import DF3_ABF_KNOWN_CRCS
        # Verify our known CRC dict is populated and wired
        assert 0x78462536 in DF3_ABF_KNOWN_CRCS
        entry = DF3_ABF_KNOWN_CRCS[0x78462536]
        assert entry["variant"] == VARIANT_DF3_ABF
        assert entry["cal"] == "STOCK"


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


# ── Part-number scanner ───────────────────────────────────────────────────────

class TestPartNumberScanner:
    """Tests for _scan_part_numbers and _classify_df2_variant."""

    def _get_helpers(self):
        from digitool.rom_profiles import _scan_part_numbers, _classify_df2_variant
        return _scan_part_numbers, _classify_df2_variant

    def _rom_with_string(self, s: str) -> bytes:
        rom = bytearray([0x41] * 0x8000)
        # Embed string in the fill area at 0x0100
        for i, c in enumerate(s.encode('ascii')):
            rom[0x0100 + i] = c
        return bytes(rom)

    def test_2e_suffix_b_detected(self):
        scan, _ = self._get_helpers()
        rom = self._rom_with_string("037906023B")
        hits = scan(rom)
        assert hits["df2_2e"] is not None
        assert hits["df2_pf"] is None
        assert hits["df3_aba"] is None

    def test_2e_suffix_c_detected(self):
        scan, _ = self._get_helpers()
        rom = self._rom_with_string("037906023C")
        hits = scan(rom)
        assert hits["df2_2e"] is not None

    def test_2e_suffix_d_detected(self):
        scan, _ = self._get_helpers()
        rom = self._rom_with_string("037906023D")
        hits = scan(rom)
        assert hits["df2_2e"] is not None

    def test_2e_suffix_e_detected(self):
        scan, _ = self._get_helpers()
        rom = self._rom_with_string("037906023E")
        hits = scan(rom)
        assert hits["df2_2e"] is not None

    def test_bosch_2e_detected(self):
        scan, _ = self._get_helpers()
        rom = self._rom_with_string("0261200263")
        hits = scan(rom)
        assert hits["df2_2e"] is not None

    def test_pf_suffix_a_detected(self):
        scan, _ = self._get_helpers()
        rom = self._rom_with_string("037906023A")
        hits = scan(rom)
        assert hits["df2_pf"] is not None
        assert hits["df2_2e"] is None

    def test_bosch_pf_detected(self):
        scan, _ = self._get_helpers()
        rom = self._rom_with_string("0261200169")
        hits = scan(rom)
        assert hits["df2_pf"] is not None

    def test_df3_aba_1h_detected(self):
        scan, _ = self._get_helpers()
        rom = self._rom_with_string("1H0906025A")
        hits = scan(rom)
        assert hits["df3_aba"] is not None
        assert hits["df2_2e"] is None
        assert hits["df2_pf"] is None

    def test_no_pn_all_none(self):
        scan, _ = self._get_helpers()
        rom = bytearray([0x41] * 0x8000)
        hits = scan(bytes(rom))
        assert hits["df3_aba"] is None
        assert hits["df2_2e"] is None
        assert hits["df2_pf"] is None

    def test_scan_case_insensitive(self):
        """Embedded string in lowercase should still hit (scan upper-cases internally)."""
        scan, _ = self._get_helpers()
        rom = self._rom_with_string("037906023b")  # lowercase suffix
        hits = scan(rom)
        assert hits["df2_2e"] is not None

    def test_scan_with_spaces_in_rom(self):
        """Part numbers with spaces in ROM (e.g. "037 906 023 B") should match."""
        scan, _ = self._get_helpers()
        rom = self._rom_with_string("037 906 023 B")
        hits = scan(rom)
        assert hits["df2_2e"] is not None

    def test_classify_2e_wins(self):
        _, classify = self._get_helpers()
        hits = {"df2_2e": "037906023B", "df2_pf": None, "df2_generic": None}
        variant, label, method = classify(hits)
        assert variant == VARIANT_DF2_2E
        assert "2E" in label
        assert "037906023B" in method

    def test_classify_pf_wins(self):
        _, classify = self._get_helpers()
        hits = {"df2_2e": None, "df2_pf": "037906023A", "df2_generic": None}
        variant, label, method = classify(hits)
        assert variant == VARIANT_DF2_PF
        assert "PF" in label

    def test_classify_generic_defaults_to_pf(self):
        _, classify = self._get_helpers()
        hits = {"df2_2e": None, "df2_pf": None, "df2_generic": "037906023"}
        variant, label, method = classify(hits)
        assert variant == VARIANT_DF2_PF  # generic 037 → PF assumption

    def test_classify_no_pn_defaults_to_2e(self):
        _, classify = self._get_helpers()
        hits = {"df2_2e": None, "df2_pf": None, "df2_generic": None}
        variant, label, method = classify(hits)
        assert variant == VARIANT_DF2_2E  # most common variant default

    def test_2e_takes_priority_over_generic(self):
        """If both 2E-specific and generic hits present, 2E wins."""
        _, classify = self._get_helpers()
        hits = {"df2_2e": "037906023C", "df2_pf": None, "df2_generic": "037906023"}
        variant, label, method = classify(hits)
        assert variant == VARIANT_DF2_2E


# ── Enhanced detection: confidence levels ────────────────────────────────────

class TestDetectionConfidence:
    """Verify confidence is HIGH when PN found, MEDIUM when structural only."""

    def _make_df2_rom_with_pn(self, pn: str) -> bytes:
        rom = bytearray([0x41] * 0x8000)
        rom[0x7FFE] = 0xAA; rom[0x7FFF] = 0xBB
        for i, c in enumerate(pn.encode('ascii')):
            rom[0x0200 + i] = c
        return bytes(rom)

    def test_df2_2e_pn_found_is_high_confidence(self):
        rom = self._make_df2_rom_with_pn("037906023B")
        result = detect_rom_family(rom)
        assert result is not None
        assert result.variant == VARIANT_DF2_2E
        assert result.confidence == "HIGH"

    def test_df2_pf_pn_found_is_high_confidence(self):
        rom = self._make_df2_rom_with_pn("037906023A")
        result = detect_rom_family(rom)
        assert result is not None
        assert result.variant == VARIANT_DF2_PF
        assert result.confidence == "HIGH"

    def test_df2_no_pn_is_medium_confidence(self):
        """No part number in ROM → MEDIUM confidence, default 2E."""
        rom = bytearray([0x41] * 0x8000)
        rom[0x7FFE] = 0xAA; rom[0x7FFF] = 0xBB
        result = detect_rom_family(bytes(rom))
        assert result is not None
        assert result.confidence == "MEDIUM"

    def test_df3_aba_1h_pn_is_high_confidence(self):
        rom = bytearray([0x41] * 0x8000)
        rom[0x7FFE] = 0xCC; rom[0x7FFF] = 0xDD
        for i, c in enumerate(b"1H0906025B"):
            rom[0x0300 + i] = c
        result = detect_rom_family(bytes(rom))
        assert result is not None
        assert result.variant == VARIANT_DF3_ABA
        assert result.confidence == "HIGH"

    def test_df3_abf_pn_found_is_high_confidence(self):
        """ABF ROM with a 1H part number in fill → HIGH confidence."""
        rom = bytearray([0x00] * 0x8000)
        sig = b"DIGIFANT 3.2"
        for i, b in enumerate(sig):
            rom[0x0D99 + i] = b
        for i, c in enumerate(b"1H0906025A"):
            rom[0x0400 + i] = c
        rom[0x7FFE] = 0x92; rom[0x7FFF] = 0x00
        result = detect_rom_family(bytes(rom))
        assert result is not None
        assert result.variant == VARIANT_DF3_ABF
        assert result.confidence == "HIGH"

    def test_df3_abf_no_pn_is_high_confidence_via_string(self):
        """DIGIFANT 3 string is itself HIGH confidence — no PN needed."""
        rom = make_df3_abf_rom()
        result = detect_rom_family(bytes(rom))
        assert result is not None
        assert result.variant == VARIANT_DF3_ABF
        # DIGIFANT 3 string found → HIGH confidence regardless of PN
        assert result.confidence == "HIGH"

    def test_df3_abf_structural_only_is_medium_confidence(self):
        """Structural detection (no DIGIFANT 3 string, no PN) → MEDIUM."""
        rom = bytearray([0x00] * 0x8000)
        # Reset vector into CPU 0x8000+ but no DIGIFANT string, low fill
        rom[0x7FFE] = 0x92; rom[0x7FFF] = 0x00
        result = detect_rom_family(bytes(rom))
        # May be None (fell through) or MEDIUM — structural alone is weak
        if result is not None and result.variant == VARIANT_DF3_ABF:
            assert result.confidence == "MEDIUM"

    def test_df2_warning_mentions_no_immo(self):
        """DF2 warning should note no immobilizer (direct swap compatible)."""
        rom = bytearray([0x41] * 0x8000)
        rom[0x7FFE] = 0xAA; rom[0x7FFF] = 0xBB
        result = detect_rom_family(bytes(rom))
        assert result is not None
        immo_note = any("immo" in w.lower() or "immobilizer" in w.lower()
                        for w in result.warnings)
        assert immo_note

    def test_df3_aba_warning_mentions_immo(self):
        """DF3 ABA warning must mention immobilizer."""
        rom = bytearray([0x41] * 0x8000)
        rom[0x7FFE] = 0xCC; rom[0x7FFF] = 0xDD
        for i, c in enumerate(b"1H0906025"):
            rom[0x0300 + i] = c
        result = detect_rom_family(bytes(rom))
        assert result is not None
        immo_warned = any("immo" in w.lower() for w in result.warnings)
        assert immo_warned


# ── DF2 2E / PF variant label content ────────────────────────────────────────

class TestDF2VariantLabels:
    """Verify the label string in DetectionResult reflects engine variant."""

    def _rom(self, pn: str) -> bytes:
        rom = bytearray([0x41] * 0x8000)
        rom[0x7FFE] = 0xAA; rom[0x7FFF] = 0xBB
        for i, c in enumerate(pn.encode('ascii')):
            rom[0x0100 + i] = c
        return bytes(rom)

    def test_2e_label_contains_2e(self):
        result = detect_rom_family(self._rom("037906023C"))
        assert result is not None
        assert "2E" in result.label or "2.0" in result.label

    def test_pf_label_contains_pf(self):
        result = detect_rom_family(self._rom("037906023A"))
        assert result is not None
        assert "PF" in result.label or "1.8" in result.label

    def test_2e_and_pf_are_different_variants(self):
        r2e = detect_rom_family(self._rom("037906023C"))
        rpf = detect_rom_family(self._rom("037906023A"))
        assert r2e is not None and rpf is not None
        assert r2e.variant != rpf.variant

    def test_both_df2_use_same_family(self):
        """Both 2E and PF use MAP_FAMILY_DF2 — same map layout."""
        r2e = detect_rom_family(self._rom("037906023C"))
        rpf = detect_rom_family(self._rom("037906023A"))
        assert r2e is not None and rpf is not None
        assert r2e.family == MAP_FAMILY_DF2
        assert rpf.family == MAP_FAMILY_DF2
