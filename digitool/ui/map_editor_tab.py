"""
ui/map_editor_tab.py
Single 16×16 map editor panel — ignition or fuel.
Includes TipPanel on the right side.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PyQt5.QtGui import QFont

from digitool.rom_profiles import MapDef
from digitool.ui.map_table import MapTable
from digitool.ui.map_tips import TipPanel


_RPM_LABELS  = ["600","800","1000","1250","1500","1750","2000","2250",
                 "2500","2750","3000","3500","4000","5000","6000","6300"]
_LOAD_LABELS = ["20","30","40","50","60","80","100","120",
                "140","160","170","180","190","200","210","220"]


class MapPanel(QWidget):
    """
    Editable 16×16 heatmap with cell info strip and TipPanel sidebar.
    map_type: 'ign' or 'fuel'
    """

    def __init__(self, title: str, map_type: str = "ign", parent=None):
        super().__init__(parent)
        self._map_def: MapDef | None = None
        self._rom:     bytearray | None = None
        self._map_type = map_type

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left: map + info strip ────────────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 8, 8)
        left_layout.setSpacing(6)

        hdr = QLabel(title)
        hdr.setFont(QFont("Segoe UI", 12, QFont.Bold))
        hdr.setStyleSheet("color: #00d4ff; margin-bottom: 4px;")
        left_layout.addWidget(hdr)

        self.table = MapTable(16, 16, map_type)
        self.table.set_axis_labels(_RPM_LABELS, _LOAD_LABELS)
        left_layout.addWidget(self.table, 1)

        info_row = QHBoxLayout()
        self.lbl_cell = QLabel("Cell: —")
        self.lbl_addr = QLabel("Addr: —")
        self.lbl_raw  = QLabel("Raw: —")
        self.lbl_val  = QLabel("Value: —")
        for lbl in [self.lbl_cell, self.lbl_addr, self.lbl_raw, self.lbl_val]:
            lbl.setStyleSheet("color: #3d5068; font-size: 11px; font-family: Consolas;")
            info_row.addWidget(lbl)
        info_row.addStretch()
        left_layout.addLayout(info_row)

        root.addWidget(left, 1)

        # ── Divider ───────────────────────────────────────────────────────────
        div = QFrame()
        div.setFrameShape(QFrame.VLine)
        div.setStyleSheet("color: #1a2332;")
        root.addWidget(div)

        # ── Right: tip panel ──────────────────────────────────────────────────
        self._tip_panel = TipPanel()
        root.addWidget(self._tip_panel)

        self.table.cell_selected.connect(self._on_cell)

    def load(self, map_def: MapDef, rom: bytearray):
        self._map_def = map_def
        self._rom     = rom
        data = list(rom[map_def.data_addr: map_def.data_addr + map_def.size])
        self.table.load_data(data)
        self._tip_panel.show_tip(map_def.name)

    def write_back(self, rom: bytearray) -> bytearray:
        if self._map_def is None:
            return rom
        data = self.table.get_data()
        start = self._map_def.data_addr
        for i, b in enumerate(data):
            rom[start + i] = b
        return rom

    def _on_cell(self, row: int, col: int, raw: int, display: float):
        addr = (self._map_def.data_addr + row * 16 + col) if self._map_def else 0
        self.lbl_cell.setText(f"Cell: [{row},{col}]")
        self.lbl_addr.setText(f"Addr: 0x{addr:04X}")
        self.lbl_raw.setText(f"Raw: {raw}")
        if self._map_type == "ign":
            self.lbl_val.setText(f"Value: {display:.1f}°BTDC")
        else:
            self.lbl_val.setText(f"Value: {raw}")

    # ── KWPBridge live overlay ────────────────────────────────────────────────

    def attach_kwp(self):
        """Enable live overlay — called when ECU matches ROM."""
        self._kwp_active   = True
        self._kwp_rpm_col  = None
        self._kwp_load_row = None
        self._kwp_o2s_rich = None

    def detach_kwp(self):
        """Disable overlay and clear highlights."""
        self._kwp_active   = False
        self._kwp_rpm_col  = None
        self._kwp_load_row = None
        self._kwp_o2s_rich = None
        self.table.clear_overlay()

    def update_overlay(self, lv):
        """Update cursor position from LiveValues. Called by MainWindow."""
        if not getattr(self, '_kwp_active', False):
            return
        if lv is None or not lv.valid:
            return

        # Digifant RPM axis (rows in map_editor_tab, matching _RPM_LABELS)
        rpm_axis  = [600, 800, 1000, 1250, 1500, 1750, 2000, 2250,
                     2500, 2750, 3000, 3500, 4000, 5000, 6000, 6300]
        # Digifant load axis — VAF raw 0-255 mapped to _LOAD_LABELS
        load_axis = [20, 30, 40, 50, 60, 80, 100, 120,
                     140, 160, 170, 180, 190, 200, 210, 220]

        new_col, new_row = None, None

        if lv.rpm is not None:
            new_col = min(range(len(rpm_axis)),
                         key=lambda i: abs(rpm_axis[i] - lv.rpm))

        if lv.load is not None:
            # Scale VAF raw 0-255 to load axis range 20-220
            load_scaled = (lv.load / 255.0) * 220
            new_row = min(range(len(load_axis)),
                         key=lambda i: abs(load_axis[i] - load_scaled))

        changed = (new_col != self._kwp_rpm_col or
                   new_row != self._kwp_load_row or
                   lv.o2s_rich != self._kwp_o2s_rich)

        self._kwp_rpm_col  = new_col
        self._kwp_load_row = new_row
        self._kwp_o2s_rich = lv.o2s_rich

        if changed:
            self.table.set_overlay(new_col, new_row, lv.o2s_rich)
