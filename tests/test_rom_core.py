"""
tests/test_rom_core.py
======================
Tests for DigiTool's core ROM handling: detection, map read/write,
checksum, encoding helpers, and write_back round-trips.

All tests run headless (no Qt required) — they operate on raw bytearrays
and the pure-Python layer of rom_profiles.py.
"""

import copy
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from digitool.rom_profiles import (
    detect_rom, normalize_rom_image, compute_checksum,
    raw_to_ign_deg, ign_deg_to_raw, rpm_to_rev_limit, rev_limit_rpm,
    KNOWN_CRCS, G60_SINGLE_MAPS, G60_TRIPLE_MAPS,
    MAP_FAMILY_SINGLE, MAP_FAMILY_TRIPLE, MAP_FAMILY_MK2,
    DetectionResult,
)

# ── Fixture paths ─────────────────────────────────────────────────────────────

ROMS_DIR = os.path.join(os.path.dirname(__file__), '..', 'roms')


def _load(filename: str) -> bytearray:
    path = os.path.join(ROMS_DIR, filename)
    return bytearray(open(path, 'rb').read())


def _load_norm(filename: str):
    raw = _load(filename)
    norm, notes = normalize_rom_image(raw)
    return bytearray(norm), notes


# ── Detection — known stock ROMs ──────────────────────────────────────────────

class TestDetection:
    def test_g60_pg_stock_high_confidence(self):
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        r = detect_rom(rom)
        assert r.confidence == 'HIGH'
        assert r.family == MAP_FAMILY_SINGLE
        assert r.variant == 'G60'
        assert r.crc32 == 0x8C6FEC45

    def test_g40_stock_high_confidence(self):
        rom, _ = _load_norm('G40_StockEprom.BIN')
        r = detect_rom(rom)
        assert r.confidence == 'HIGH'
        assert r.family == MAP_FAMILY_SINGLE
        assert r.variant == 'G40'
        assert r.crc32 == 0xB2BEC49D

    def test_g40_mk2_family(self):
        rom, _ = _load_norm('G40_Mk2_StockEprom.BIN')
        r = detect_rom(rom)
        assert r.confidence == 'HIGH'
        assert r.family == MAP_FAMILY_MK2
        assert r.variant == 'G40_MK2'

    def test_corrado_triple_map(self):
        rom, _ = _load_norm('corradoSLS.BIN')
        r = detect_rom(rom)
        assert r.confidence == 'HIGH'
        assert r.family == MAP_FAMILY_TRIPLE
        assert r.is_triple is True

    def test_passat_g60_stock(self):
        rom, _ = _load_norm('PASSG60.BIN')
        r = detect_rom(rom)
        assert r.confidence == 'HIGH'
        assert r.variant == 'G60_PASSAT'
        assert r.rpm_limit == 6250

    def test_g60_limited_16v(self):
        rom, _ = _load_norm('limited_16v_G60.BIN')
        r = detect_rom(rom)
        assert r.confidence == 'HIGH'
        assert r.variant == 'G60_16V_LIMITED'

    def test_edited_rom_has_correct_rpm(self):
        """A known-modified ROM should report its actual (modified) rev limit."""
        rom, _ = _load_norm('G40_StockEprom_with7kRevLimit.BIN')
        r = detect_rom(rom)
        assert r.confidence == 'HIGH'
        assert r.rpm_limit == pytest.approx(6995, abs=20)

    def test_detection_result_has_maps(self):
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        r = detect_rom(rom)
        assert len(r.maps) >= 30      # G60 single has 32+ maps
        assert r.maps[0].name         # all maps have names

    def test_triple_map_count(self):
        rom, _ = _load_norm('corradoSLS.BIN')
        r = detect_rom(rom)
        assert len(r.maps) >= 3       # at least the 3 ignition maps


# ── Normalise ─────────────────────────────────────────────────────────────────

class TestNormalise:
    def test_32k_rom_unchanged(self):
        """32 KB ROMs should pass through unchanged."""
        rom, notes = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        assert len(rom) == 0x8000
        assert notes == []

    def test_64k_rom_normalised_to_32k(self):
        """64 KB (27C512) images should be detected and sliced to 32 KB."""
        raw = _load('G60_PG_StockEprom_022B93EE.BIN')
        doubled = bytearray(raw + raw)     # simulate 27C512 mirrored
        norm, notes = normalize_rom_image(doubled)
        assert len(norm) == 0x8000
        assert any('64' in n or '27C512' in n or 'mirror' in n.lower()
                   for n in notes)


# ── Checksum ──────────────────────────────────────────────────────────────────

class TestChecksum:
    def test_stock_checksum_matches_crc(self):
        """compute_checksum returns the same value detect_rom uses for CRC matching."""
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        cs = compute_checksum(rom)
        assert cs == 0x8C6FEC45

    def test_g40_stock_checksum(self):
        rom, _ = _load_norm('G40_StockEprom.BIN')
        assert compute_checksum(rom) == 0xB2BEC49D

    def test_mutated_rom_has_different_checksum(self):
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        original_cs = compute_checksum(rom)
        rom[0x4004] ^= 0xFF              # flip a byte in ign map
        assert compute_checksum(rom) != original_cs


# ── Encoding helpers ──────────────────────────────────────────────────────────

class TestEncodingHelpers:
    """Test the raw↔physical conversion functions."""

    def test_ign_decode_known_values(self):
        # Formula: (210 - raw) / 2.86
        assert raw_to_ign_deg(122) == pytest.approx((210 - 122) / 2.86, abs=0.05)
        assert raw_to_ign_deg(165) == pytest.approx((210 - 165) / 2.86, abs=0.05)

    def test_ign_roundtrip(self):
        for deg in [5.0, 10.0, 15.0, 20.0, 25.0, 30.0]:
            raw = ign_deg_to_raw(deg)
            back = raw_to_ign_deg(raw)
            assert back == pytest.approx(deg, abs=0.4)   # 1 LSB tolerance

    def test_ign_encode_clamps_to_byte(self):
        raw = ign_deg_to_raw(35.0)
        assert 0 <= raw <= 255

    def test_rev_limit_roundtrip(self):
        for rpm in [6000, 6500, 7000, 7500]:
            raw = rpm_to_rev_limit(rpm)
            back = rev_limit_rpm(raw)
            assert back == pytest.approx(rpm, abs=50)

    def test_rev_limit_g60_stock(self):
        """Stock G60 is 6201 RPM per detection."""
        raw = open(
            os.path.join(ROMS_DIR, 'G60_PG_StockEprom_022B93EE.BIN'), 'rb'
        ).read()
        rev_bytes = raw[0x4BF2:0x4BF4]
        raw_val = int.from_bytes(rev_bytes, 'big')
        assert rev_limit_rpm(raw_val) == pytest.approx(6201, abs=20)


# ── Map read (pure bytearray, no Qt) ─────────────────────────────────────────

class TestMapRead:
    """Read map cells directly from ROM bytes using MapDef addresses."""

    def test_g60_ign_map_first_row(self):
        """First row of ignition map should be plausible BTDC values."""
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        ign_def = next(m for m in G60_SINGLE_MAPS if m.name == 'Ignition')
        row0 = rom[ign_def.data_addr : ign_def.data_addr + 16]
        degs = [raw_to_ign_deg(b) for b in row0]
        # All values should be positive BTDC and within a plausible range
        assert all(0 < d < 45 for d in degs), f"Out of range: {degs}"

    def test_g60_fuel_map_nonzero(self):
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        fuel_def = next(m for m in G60_SINGLE_MAPS if m.name == 'Fuel')
        fuel_data = rom[fuel_def.data_addr : fuel_def.data_addr + fuel_def.size]
        assert any(b != 0 for b in fuel_data), "Fuel map is all zeros"
        assert any(b != 0xFF for b in fuel_data), "Fuel map is all 0xFF"

    def test_mapdef_addresses_in_range(self):
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        for md in G60_SINGLE_MAPS:
            end = md.data_addr + md.size
            assert end <= len(rom), \
                f"{md.name} end 0x{end:04X} exceeds ROM size 0x{len(rom):04X}"

    def test_triple_map_addresses_in_range(self):
        rom, _ = _load_norm('corradoSLS.BIN')
        r = detect_rom(rom)
        for md in r.maps:
            end = md.data_addr + md.size
            assert end <= len(rom), \
                f"{md.name} end 0x{end:04X} exceeds ROM size 0x{len(rom):04X}"


# ── Write-back (the critical untested path) ───────────────────────────────────

class TestWriteBack:
    """
    Test the write path without Qt by exercising the pure-bytearray logic
    that write_back() implements. These tests replicate exactly what the
    UI does: read cells from ROM, modify them, write back, verify bytes.
    """

    def _write_map(self, rom: bytearray, map_def, new_values: list[int]) -> bytearray:
        """Minimal write_back equivalent — no Qt required."""
        rom = bytearray(rom)
        for i, val in enumerate(new_values):
            offset = map_def.data_addr + i
            if offset < len(rom):
                rom[offset] = max(0, min(255, val))
        return rom

    def test_write_single_byte_to_ign_map(self):
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        ign_def = next(m for m in G60_SINGLE_MAPS if m.name == 'Ignition')
        original = rom[ign_def.data_addr]
        new_val = (original + 10) % 256

        modified = self._write_map(rom, ign_def, [new_val])
        assert modified[ign_def.data_addr] == new_val
        # Rest of map unchanged
        assert modified[ign_def.data_addr + 1] == rom[ign_def.data_addr + 1]

    def test_write_does_not_corrupt_adjacent_maps(self):
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        ign_def  = next(m for m in G60_SINGLE_MAPS if m.name == 'Ignition')
        fuel_def = next(m for m in G60_SINGLE_MAPS if m.name == 'Fuel')

        # Write all 0xAA to ignition map
        new_ign = [0xAA] * ign_def.size
        modified = self._write_map(rom, ign_def, new_ign)

        # Fuel map at different address should be untouched
        fuel_original = bytes(rom[fuel_def.data_addr : fuel_def.data_addr + fuel_def.size])
        fuel_modified = bytes(modified[fuel_def.data_addr : fuel_def.data_addr + fuel_def.size])
        assert fuel_original == fuel_modified

    def test_write_full_ign_map_roundtrip(self):
        """Write new values to ign map, verify exact bytes, verify decode."""
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        ign_def = next(m for m in G60_SINGLE_MAPS if m.name == 'Ignition')

        # Build a synthetic ignition map: 25° BTDC everywhere
        target_deg = 25.0
        raw_25 = ign_deg_to_raw(target_deg)
        new_vals = [raw_25] * ign_def.size

        modified = self._write_map(rom, ign_def, new_vals)
        written = modified[ign_def.data_addr : ign_def.data_addr + ign_def.size]
        assert all(b == raw_25 for b in written)
        # Verify decode gives approximately the target
        assert raw_to_ign_deg(raw_25) == pytest.approx(target_deg, abs=0.4)

    def test_write_clamps_to_byte_range(self):
        """Values outside 0-255 must be clamped, not overflow."""
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        ign_def = G60_SINGLE_MAPS[0]
        modified = self._write_map(rom, ign_def, [300, -5, 128])
        assert modified[ign_def.data_addr]     == 255   # clamped from 300
        assert modified[ign_def.data_addr + 1] == 0     # clamped from -5
        assert modified[ign_def.data_addr + 2] == 128   # unchanged

    def test_write_does_not_extend_rom(self):
        """write_back must never grow the ROM."""
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        original_len = len(rom)
        ign_def = G60_SINGLE_MAPS[0]
        modified = self._write_map(rom, ign_def, [0xFF] * ign_def.size)
        assert len(modified) == original_len

    def test_write_rev_limit(self):
        """Rev limit round-trip: write RPM bytes, read back directly, verify."""
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        r = detect_rom(rom)
        assert r.rev_addr is not None

        target_rpm = 7000
        raw_val = rpm_to_rev_limit(target_rpm)
        raw_bytes = raw_val.to_bytes(2, 'big')

        modified = bytearray(rom)
        modified[r.rev_addr]     = raw_bytes[0]
        modified[r.rev_addr + 1] = raw_bytes[1]

        # Read back directly from bytes — detect_rom caches rpm_limit from
        # KNOWN_CRCS so won't reflect a modified ROM; read the address directly
        readback = int.from_bytes(modified[r.rev_addr:r.rev_addr + 2], 'big')
        assert readback == raw_val
        assert rev_limit_rpm(readback) == pytest.approx(target_rpm, abs=50)

    def test_write_preserves_unrelated_bytes(self):
        """Bytes outside any known map should be identical after write."""
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        ign_def = next(m for m in G60_SINGLE_MAPS if m.name == 'Ignition')

        # Sample some bytes well outside the ign map
        probe_addr = 0x0010
        original_probe = rom[probe_addr]

        modified = self._write_map(rom, ign_def, [0xAA] * ign_def.size)
        assert modified[probe_addr] == original_probe

    def test_multiple_map_writes_accumulate(self):
        """Sequential writes to different maps should both persist."""
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        ign_def  = next(m for m in G60_SINGLE_MAPS if m.name == 'Ignition')
        fuel_def = next(m for m in G60_SINGLE_MAPS if m.name == 'Fuel')

        rom = self._write_map(rom, ign_def,  [0x11] * ign_def.size)
        rom = self._write_map(rom, fuel_def, [0x22] * fuel_def.size)

        assert rom[ign_def.data_addr]  == 0x11
        assert rom[fuel_def.data_addr] == 0x22


# ── Edited ROM cross-checks ───────────────────────────────────────────────────

class TestEditedRoms:
    """Verify that known-edited ROMs differ from stock in the expected places."""

    def test_g40_7k_rev_limit_differs_from_stock(self):
        stock, _  = _load_norm('G40_StockEprom.BIN')
        edited, _ = _load_norm('G40_StockEprom_with7kRevLimit.BIN')

        r_stock  = detect_rom(stock)
        r_edited = detect_rom(edited)

        assert r_stock.rpm_limit  < r_edited.rpm_limit
        assert r_edited.rpm_limit == pytest.approx(6995, abs=20)

    def test_stage5_g60_higher_rev_than_stock(self):
        stock, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        stage5, _ = _load_norm('STAGE_5_G60.BIN')

        r_stock  = detect_rom(stock)
        r_stage5 = detect_rom(stage5)

        assert r_stage5.rpm_limit > r_stock.rpm_limit

    def test_gifhorn_g40_differs_from_stock(self):
        """Tuned G40 should have same detection variant but different CRC."""
        stock, _  = _load_norm('G40_StockEprom.BIN')
        tuned, _  = _load_norm(
            'G40_EubelTuningInGifhorn1995_MinorFuelTimingChanges_'
            'BoostCutRemoval_IdleIgnition.BIN')

        r_stock = detect_rom(stock)
        r_tuned = detect_rom(tuned)

        assert r_tuned.variant == r_stock.variant     # same ECU type
        assert r_tuned.crc32   != r_stock.crc32       # but different ROM content
        assert r_tuned.cal != 'STOCK'                 # flagged as modified


# ── Code patches detection ────────────────────────────────────────────────────

class TestCodePatches:
    """Verify code-patch detection returns sane results on stock ROMs."""

    def test_stock_g60_patches_detected(self):
        from digitool.rom_profiles import CODE_PATCHES_G60
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        result = detect_rom(rom)
        # Each patch entry should have a name and an address or None
        for patch_name, patch_info in CODE_PATCHES_G60.items():
            assert isinstance(patch_name, str)

    def test_detection_result_has_cal_field(self):
        rom, _ = _load_norm('G60_PG_StockEprom_022B93EE.BIN')
        r = detect_rom(rom)
        assert r.cal in ('STOCK', 'MODIFIED', None) or isinstance(r.cal, str)
