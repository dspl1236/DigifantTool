"""
ui/hex_tab.py
Full hex dump view with region highlight labels.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QLabel
)
from PyQt5.QtGui import QFont

from digitool.rom_profiles import DetectionResult


# Regions to highlight in the hex view (G60 single-map)
_REGIONS_SINGLE = [
    (0x4004, 0x4103, "#1a3020", "Ignition Map"),
    (0x4104, 0x4203, "#1a2030", "Fuel Map"),
    (0x4BF2, 0x4BF3, "#2a1a10", "Rev Limit"),
    (0x4433, 0x4436, "#2a2010", "Digilag Patch"),
    (0x6269, 0x626B, "#2a1020", "Open Loop Lambda"),
    (0x6287, 0x6289, "#1a2020", "ISV Disable"),
]

_REGIONS_TRIPLE = [
    (0x4000, 0x40FF, "#1a3020", "Ign Map 1"),
    (0x4100, 0x41FF, "#162a1a", "Ign Map 2"),
    (0x4200, 0x42FF, "#122414", "Ign Map 3"),
    (0x4300, 0x43FF, "#1a2030", "Fuel Map"),
    (0x4456, 0x4457, "#2a1a10", "Rev Limit"),
]

_REGIONS_MK2 = [
    (0x50A0, 0x519F, "#1a3020", "Ignition Map"),
    (0x51A0, 0x529F, "#1a2030", "Fuel Map"),
]


class HexTab(QWidget):
    """Hex dump of the loaded ROM with region labels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rom: bytes | None = None
        self._result: DetectionResult | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Toolbar
        bar = QHBoxLayout()
        self.lbl_info = QLabel("No ROM loaded")
        self.lbl_info.setStyleSheet("color: #3d5068; font-size: 11px; font-family: Consolas;")
        bar.addWidget(self.lbl_info)
        bar.addStretch()
        root.addLayout(bar)

        # Hex display
        self.txt = QPlainTextEdit()
        self.txt.setReadOnly(True)
        self.txt.setFont(QFont("Consolas", 10))
        self.txt.setStyleSheet(
            "background: #0d1117; color: #bccdd8; border: 1px solid #1a2332;"
        )
        root.addWidget(self.txt)

        # Region legend
        self.legend = QLabel("")
        self.legend.setStyleSheet("color: #3d5068; font-size: 10px; font-family: Consolas;")
        self.legend.setWordWrap(True)
        root.addWidget(self.legend)

    def load_rom(self, result: DetectionResult, rom: bytes):
        self._result = result
        self._rom    = rom
        self.lbl_info.setText(
            f"{result.label}  ·  {len(rom):,} bytes  ·  CRC32: {result.crc32:#010x}"
        )
        self._render()

    def _render(self):
        if not self._rom:
            return

        rom = self._rom
        lines = []
        for off in range(0, len(rom), 16):
            chunk = rom[off:off + 16]
            hex_  = " ".join(f"{b:02X}" for b in chunk)
            asc   = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{off:04X}  {hex_:<47}  {asc}")

        self.txt.setPlainText("\n".join(lines))

        # Region legend
        if self._result:
            regions = self._get_regions()
            legend_parts = [f"  [{s:04X}–{e:04X}] {name}" for s, e, _, name in regions]
            self.legend.setText("Regions: " + "   ".join(legend_parts))

    def _get_regions(self):
        if not self._result:
            return []
        if self._result.is_triple:
            return _REGIONS_TRIPLE
        if self._result.is_mk2:
            return _REGIONS_MK2
        return _REGIONS_SINGLE
