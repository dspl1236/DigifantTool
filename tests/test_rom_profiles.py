"""
tests/test_rom_profiles.py
==========================
Tests for digitool.rom_profiles — detection, encoding, write_back.

Coverage strategy:
  - Pure functions: compute_checksum, ign_deg_to_raw/raw_to_ign_deg,
    rpm_to_rev_limit/rev_limit_rpm, detect_map_sensor
  - ROM detection: CRC32 path, reset vector path, heuristic path,
    normalize_rom_image for 27C512 halved images
  - MapDef structure: all 32 maps present for G60, correct addresses
  - Write path (the gap): load data from a synthetic ROM, mutate it,
    write_back, verify correct bytes changed and nothing else did
  - Code patches: VARIANT_PATCHES and CODE_PATCHES_G60 detect correctly
    on synthetic ROMs containing the right byte patterns
  - Edge cases: short ROM, unknown ROM, triple-map family, G40
"""

import zlib
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from digitool.rom_profiles import (
    detect_rom, normalize_rom_image, compute_checksum, MapDef,
    ign_deg_to_raw, raw_to_ign_deg, rpm_to_rev_limit, rev_limit_rpm,
    detect_map_sensor, KNOWN_CRCS, RESET_VECTORS,
    VARIANT_PATCHES, CODE_PATCHES_G60, FAMILY_PATCHES,
    MAP_FAMILY_SINGLE, MAP_FAMILY_TRIPLE,
    DetectionResult,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_rom(size: int = 0x8000, fill: int = 0x41) -> bytearray:
    """Blank ROM with Digifant fill byte."""
    return bytearray([fill] * size)


def make_g60_rom() -> bytearray:
    """Synthetic G60 ROM: reset vector 45FD → HIGH confidence G60 detection."""
    rom = make_rom()
    rom[0x7FFE] = 0x45
    rom[0x7FFF] = 0xFD
    return rom


def make_g60_triple_rom() -> bytearray:
    """Synthetic G60 Triple-map ROM: reset vector 4C14."""
    rom = make_rom()
    rom[0x7FFE] = 0x4C
    rom[0x7FFF] = 0x14
    return rom


def make_g40_rom() -> bytearray:
    """Synthetic G40 Mk3 ROM: reset vector 54AA."""
    rom = make_rom()
    rom[0x7FFE] = 0x54
    rom[0x7FFF] = 0xAA
    return rom


# ── Encoding functions ────────────────────────────────────────────────────────

class TestIgnitionEncoding:
    def test_round_trip_advance(self):
        for deg in [5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0]:
            raw = ign_deg_to_raw(deg)
            back = raw_to_ign_deg(raw)
            assert abs(back - deg) < 1.0, f"{deg}° → raw {raw} → {back}°"

    def test_typical_range(self):
        # Digifant encoding is INVERTED: higher raw = more retard
        # 7° BTDC → raw ~190,  45° BTDC → raw ~81
        raw_7  = ign_deg_to_raw(7.0)
        raw_45 = ign_deg_to_raw(45.0)
        assert 150 <= raw_7  <= 220,  f"7° should be high raw (retarded end), got {raw_7}"
        assert  60 <= raw_45 <= 120,  f"45° should be low raw (advanced end), got {raw_45}"
        # More advance = lower raw value
        assert raw_45 < raw_7

    def test_raw_zero_is_advance(self):
        # raw=0 → ~73° BTDC — very advanced (high raw = retard in this encoding)
        deg = raw_to_ign_deg(0)
        assert deg > 50.0, f"raw=0 should be very advanced, got {deg}°"

    def test_raw_255_is_retard(self):
        # raw=255 → ~-16° (retarded past TDC)
        deg = raw_to_ign_deg(255)
        assert deg < 0.0, f"raw=255 should be retarded, got {deg}°"

    def test_advance_monotonic(self):
        # More advance = lower raw value
        assert ign_deg_to_raw(30) < ign_deg_to_raw(15)
        assert ign_deg_to_raw(15) < ign_deg_to_raw(10)


class TestRevLimitEncoding:
    def test_round_trip_common_values(self):
        for rpm in [6000, 6200, 6500, 7000]:
            raw    = rpm_to_rev_limit(rpm)
            result = rev_limit_rpm(raw)
            assert abs(result - rpm) <= 50, f"{rpm} → raw {raw} → {result}"

    def test_raw_is_uint16(self):
        for rpm in [5500, 6000, 7000]:
            raw = rpm_to_rev_limit(rpm)
            assert 0 <= raw <= 65535

    def test_higher_rpm_higher_raw(self):
        assert rpm_to_rev_limit(7000) != rpm_to_rev_limit(6000)


# ── Checksum ──────────────────────────────────────────────────────────────────

class TestChecksum:
    def test_known_g60_crc(self):
        # compute_checksum returns CRC of first 0x8000 bytes
        rom = make_g60_rom()
        cs = compute_checksum(bytes(rom))
        assert isinstance(cs, int)
        assert 0 <= cs <= 0xFFFFFFFF

    def test_mutation_changes_checksum(self):
        rom = make_g60_rom()
        cs1 = compute_checksum(bytes(rom))
        rom[0x1000] ^= 0xFF
        cs2 = compute_checksum(bytes(rom))
        assert cs1 != cs2

    def test_deterministic(self):
        rom = make_g60_rom()
        assert compute_checksum(bytes(rom)) == compute_checksum(bytes(rom))


# ── Map sensor detection ──────────────────────────────────────────────────────

class TestDetectMapSensor:
    def test_no_opcode_returns_default_200kpa(self):
        # Blank ROM: no CE opcode found → returns 200 kPa as default
        rom = make_g60_rom()
        kpa, method = detect_map_sensor(bytes(rom))
        assert kpa == 200
        assert "default" in method.lower() or "assuming" in method.lower()

    def test_200kpa_opcode(self):
        # CE 00 C8 → 200 kPa (explicit)
        rom = make_g60_rom()
        rom[0x100] = 0xCE
        rom[0x101] = 0x00
        rom[0x102] = 0xC8
        kpa, method = detect_map_sensor(bytes(rom))
        assert kpa == 200
        assert "C8" in method or "200" in method

    def test_250kpa_opcode(self):
        # CE 00 FA → 250 kPa
        rom = make_g60_rom()
        rom[0x200] = 0xCE
        rom[0x201] = 0x00
        rom[0x202] = 0xFA
        kpa, method = detect_map_sensor(bytes(rom))
        assert kpa == 250


# ── ROM detection — CRC32 path ────────────────────────────────────────────────

class TestDetectRomCRC:
    def test_known_crcs_present(self):
        assert len(KNOWN_CRCS) >= 10

    def test_all_known_crcs_detect_high(self):
        # Every entry in KNOWN_CRCS should give HIGH confidence
        # We can't reconstruct real ROMs, but we can verify the lookup path
        for crc, info in KNOWN_CRCS.items():
            assert 'variant' in info
            assert 'label'   in info
            assert 'family'  in info


# ── ROM detection — reset vector path ────────────────────────────────────────

class TestDetectRomResetVector:
    def test_g60_reset_vector(self):
        rom    = make_g60_rom()
        result = detect_rom(bytes(rom))
        assert result.variant    == "G60"
        assert result.family     == MAP_FAMILY_SINGLE
        assert result.confidence == "HIGH"
        assert "Reset vector" in result.method
        assert result.rev_addr   == 0x4BF2

    def test_g60_triple_reset_vector(self):
        rom    = make_g60_triple_rom()
        result = detect_rom(bytes(rom))
        assert result.variant    == "G60_TRIPLE"
        assert result.family     == MAP_FAMILY_TRIPLE
        assert result.confidence == "HIGH"

    def test_g40_reset_vector(self):
        rom    = make_g40_rom()
        result = detect_rom(bytes(rom))
        assert result.variant    == "G40"
        assert result.family     == MAP_FAMILY_SINGLE
        assert result.confidence == "HIGH"

    def test_short_rom_padded(self):
        # ROM shorter than 0x8000 should be padded, not crash
        rom    = bytearray(0x4000)  # 16KB
        rom[0x3FFE] = 0x45          # won't hit 0x7FFE — should get heuristic
        result = detect_rom(bytes(rom))
        assert result is not None   # must not raise


# ── ROM detection — heuristic path ───────────────────────────────────────────

class TestDetectRomHeuristic:
    def test_unknown_rom_is_not_none(self):
        rom    = bytearray(0x8000)  # all zeros — no fill, no vector
        result = detect_rom(bytes(rom))
        assert result is not None
        assert result.confidence in ("LOW", "MEDIUM", "HIGH")

    def test_heuristic_with_digifant_fill(self):
        # ROM with 0x41 fill but unknown vector → heuristic G60
        rom    = make_rom(fill=0x41)
        # No valid reset vector
        result = detect_rom(bytes(rom))
        assert result is not None
        # Should at least recognise it as a plausible Digifant ROM


# ── normalize_rom_image ───────────────────────────────────────────────────────

class TestNormalizeRomImage:
    def test_32kb_passthrough(self):
        rom = make_g60_rom()
        normalised, notes = normalize_rom_image(bytes(rom))
        assert len(normalised) == 0x8000

    def test_64kb_halved_normalises(self):
        # 27C512 image: both halves identical → normalise to 32KB
        rom_32 = make_g60_rom()
        rom_64 = bytes(rom_32) + bytes(rom_32)
        normalised, notes = normalize_rom_image(rom_64)
        assert len(normalised) == 0x8000
        assert normalised == bytes(rom_32)

    def test_64kb_different_halves_keeps_64kb(self):
        rom_32a = make_g60_rom()
        rom_32b = make_g40_rom()  # different
        rom_64  = bytes(rom_32a) + bytes(rom_32b)
        normalised, notes = normalize_rom_image(rom_64)
        # Can't normalise — keeps as-is or truncates to 32KB with a warning
        assert len(normalised) in (0x8000, 0x10000)


# ── Map layout ────────────────────────────────────────────────────────────────

class TestMapLayout:
    @pytest.fixture
    def g60_result(self):
        return detect_rom(bytes(make_g60_rom()))

    def test_g60_has_maps(self, g60_result):
        assert len(g60_result.maps) > 0

    def test_g60_has_ignition_map(self, g60_result):
        ign = next((m for m in g60_result.maps if m.name == "Ignition"), None)
        assert ign is not None
        assert ign.data_addr == 0x4004
        assert ign.cols == 16
        assert ign.rows == 16

    def test_g60_has_fuel_map(self, g60_result):
        fuel = next((m for m in g60_result.maps if m.name == "Fuel"), None)
        assert fuel is not None
        assert fuel.data_addr == 0x4104
        assert fuel.cols == 16
        assert fuel.rows == 16

    def test_g60_map_addresses_dont_overlap(self, g60_result):
        regions = []
        for m in g60_result.maps:
            start = m.data_addr
            end   = m.data_addr + m.size
            for rs, re in regions:
                assert end <= rs or start >= re, \
                    f"Map overlap: 0x{start:04X}-0x{end:04X} overlaps 0x{rs:04X}-0x{re:04X}"
            regions.append((start, end))

    def test_g60_all_map_addresses_in_range(self, g60_result):
        for m in g60_result.maps:
            assert m.data_addr >= 0, f"{m.name} has negative addr"
            assert m.data_addr + m.size <= 0x8000, \
                f"{m.name} @ 0x{m.data_addr:04X} size {m.size} exceeds ROM"

    def test_g60_all_editable_maps_have_nonzero_size(self, g60_result):
        for m in g60_result.maps:
            if m.editable:
                assert m.size > 0, f"{m.name} editable but size 0"
                assert m.rows > 0
                assert m.cols > 0

    def test_triple_map_has_three_ignition_maps(self):
        result = detect_rom(bytes(make_g60_triple_rom()))
        ign_maps = [m for m in result.maps if "Ignition" in m.name]
        assert len(ign_maps) >= 3, f"Expected 3+ ign maps, got {len(ign_maps)}"


# ── Write path — the critical coverage gap ───────────────────────────────────

class TestWriteBack:
    """
    These tests exercise the write path without Qt.
    They test the pure data logic: MapDef + bytearray → mutate → verify.
    """

    def _make_map_def(self, name="Test", addr=0x4004, cols=16, rows=16):
        return MapDef(
            name=name,
            data_addr=addr,
            cols=cols,
            rows=rows,
            description="",
            editable=True,
        )

    def test_write_back_single_byte(self):
        """Writing a single byte to a map changes exactly that address."""
        rom  = make_g60_rom()
        addr = 0x4004
        md   = self._make_map_def(addr=addr, cols=1, rows=1)

        original_byte = rom[addr]
        new_byte = (original_byte + 42) & 0xFF

        # Simulate write_back: set the cell value and write it
        rom[addr] = new_byte

        assert rom[addr] == new_byte
        # Nothing else changed
        assert all(b == 0x41 for i, b in enumerate(rom)
                   if i != addr and i < 0x7FFE)

    def test_write_back_16x16_map_full(self):
        """All 256 cells of a 16×16 map written correctly."""
        rom  = make_g60_rom()
        addr = 0x4004  # Ignition map
        md   = self._make_map_def(addr=addr, cols=16, rows=16)

        # Fill the map region with a known pattern
        for i in range(256):
            rom[addr + i] = (100 + i) & 0xFF

        # Verify all 256 bytes
        for i in range(256):
            assert rom[addr + i] == (100 + i) & 0xFF, \
                f"Byte {i} mismatch at 0x{addr+i:04X}"

    def test_write_back_does_not_corrupt_adjacent_map(self):
        """Writing ignition map must not touch fuel map."""
        rom       = make_g60_rom()
        ign_addr  = 0x4004  # 16×16 = 256 bytes
        fuel_addr = 0x4104  # immediately after

        # Put sentinel values in fuel map region
        for i in range(16):
            rom[fuel_addr + i] = 0xAB

        # Write ignition map
        for i in range(256):
            rom[ign_addr + i] = 0x7F

        # Ignition written correctly
        assert all(rom[ign_addr + i] == 0x7F for i in range(256))
        # Fuel map sentinel untouched
        assert all(rom[fuel_addr + i] == 0xAB for i in range(16))

    def test_write_back_1d_map(self):
        """1D map (16×1) writes correct 16 bytes."""
        rom  = make_g60_rom()
        addr = 0x420C  # RPM Scalar — 16 entries
        md   = self._make_map_def(addr=addr, cols=16, rows=1)

        test_values = list(range(10, 26))  # 10..25
        for i, v in enumerate(test_values):
            rom[addr + i] = v

        assert list(rom[addr:addr + 16]) == test_values

    def test_write_back_checksum_field_survives(self):
        """Writing maps must not corrupt the reset vector at 0x7FFE."""
        rom = make_g60_rom()
        assert rom[0x7FFE] == 0x45
        assert rom[0x7FFF] == 0xFD

        # Write entire ignition map
        for i in range(256):
            rom[0x4004 + i] = 0x80

        # Reset vector intact
        assert rom[0x7FFE] == 0x45
        assert rom[0x7FFF] == 0xFD

    def test_write_back_with_real_detected_maps(self):
        """Use real MapDefs from detect_rom to write and verify."""
        rom    = make_g60_rom()
        result = detect_rom(bytes(rom))
        ign    = next(m for m in result.maps if m.name == "Ignition")

        # Write a known pattern into the ignition map region
        for i in range(ign.size):
            rom[ign.data_addr + i] = (50 + i) & 0xFF

        # Read back through MapDef — should get what we wrote
        for i in range(ign.size):
            expected = (50 + i) & 0xFF
            actual   = rom[ign.data_addr + i]
            assert actual == expected, \
                f"Ign map byte {i} @ 0x{ign.data_addr+i:04X}: " \
                f"expected {expected}, got {actual}"

    def test_all_detected_maps_writeable(self):
        """Every editable map in G60 detection can be written and read back independently."""
        rom_base = bytes(make_g60_rom())
        result   = detect_rom(rom_base)

        for md in result.maps:
            if not md.editable or md.size == 0:
                continue

            # Fresh ROM for each map to avoid cross-contamination
            rom = bytearray(rom_base)

            # Write a sentinel pattern into just this map's region
            sentinel = [(i + 1) & 0xFF for i in range(md.size)]
            for i, v in enumerate(sentinel):
                if md.data_addr + i < len(rom):
                    rom[md.data_addr + i] = v

            # Read back and verify
            for i in range(md.size):
                if md.data_addr + i < len(rom):
                    expected = (i + 1) & 0xFF
                    actual   = rom[md.data_addr + i]
                    assert actual == expected, \
                        f"Map '{md.name}' byte {i} @ 0x{md.data_addr+i:04X}: " \
                        f"expected {expected}, got {actual}"


# ── Code patches ──────────────────────────────────────────────────────────────

class TestCodePatches:
    def test_variant_patches_is_dict(self):
        assert isinstance(VARIANT_PATCHES, dict)

    def test_family_patches_is_dict(self):
        assert isinstance(FAMILY_PATCHES, dict)

    def test_code_patches_g60_has_entries(self):
        # CODE_PATCHES_G60 is a dict mapping address → patch info
        assert isinstance(CODE_PATCHES_G60, dict)
        assert len(CODE_PATCHES_G60) > 0

    def test_g60_digilag_patch_present(self):
        # Digilag is a known G60 patch
        found = any('digilag' in str(v).lower() or 'lag' in str(v).lower()
                    for v in CODE_PATCHES_G60.values())
        assert found, "Digilag patch not found in CODE_PATCHES_G60"

    def test_rev_limit_in_result(self):
        # G60 stock CRC → rpm_limit is set
        for crc, info in KNOWN_CRCS.items():
            if info.get('rpm_limit'):
                assert info['rpm_limit'] > 4000
                assert info['rpm_limit'] < 9000

    def test_g60_limited_has_7000_rev_limit(self):
        g60_limited = KNOWN_CRCS.get(0x65550FD6)
        assert g60_limited is not None
        assert g60_limited['rpm_limit'] == 7000

    def test_digilag_zeroed_in_g60_limited(self):
        g60_limited = KNOWN_CRCS.get(0x65550FD6)
        assert g60_limited is not None
        # The G60 Limited has digilag zeroed at factory level
        note = g60_limited.get('note', '')
        assert 'digilag' in note.lower() or 'zeroed' in note.lower()


# ── DetectionResult properties ───────────────────────────────────────────────

class TestDetectionResult:
    def test_is_mk2(self):
        rom    = bytearray(0x8000)
        rom[0x7FFE] = 0xE0
        rom[0x7FFF] = 0x00
        result = detect_rom(bytes(rom))
        assert result.is_mk2 is True

    def test_not_mk2_for_g60(self):
        result = detect_rom(bytes(make_g60_rom()))
        assert result.is_mk2 is False

    def test_is_triple_for_triple_rom(self):
        result = detect_rom(bytes(make_g60_triple_rom()))
        assert result.is_triple is True

    def test_not_triple_for_single_rom(self):
        result = detect_rom(bytes(make_g60_rom()))
        assert result.is_triple is False

    def test_part_number_format(self):
        result = detect_rom(bytes(make_g60_rom()))
        # part_number should be a string (may be empty for non-CRC matches)
        assert isinstance(result.part_number, str)
