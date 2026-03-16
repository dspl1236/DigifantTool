"""
ui/diff_tab.py
ROM diff tool — compare two .BIN files byte-by-byte, grouped by map region.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QFont

from digitool.rom_profiles import detect_rom, DetectionResult


class DiffTab(QWidget):
    """Load two ROMs and show byte-by-byte differences grouped by region."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rom_a: bytes | None = None
        self._rom_b: bytes | None = None
        self._res_a: DetectionResult | None = None
        self._res_b: DetectionResult | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Load buttons
        load_row = QHBoxLayout()
        self.btn_a   = QPushButton("⊕  Load ROM A (base)")
        self.btn_b   = QPushButton("⊕  Load ROM B (compare)")
        self.btn_diff = QPushButton("⟳  Run Diff")
        self.btn_diff.setEnabled(False)
        self.btn_a.clicked.connect(lambda: self._load_rom("a"))
        self.btn_b.clicked.connect(lambda: self._load_rom("b"))
        self.btn_diff.clicked.connect(self._run_diff)
        load_row.addWidget(self.btn_a)
        load_row.addWidget(self.btn_b)
        load_row.addStretch()
        load_row.addWidget(self.btn_diff)
        root.addLayout(load_row)

        # Labels
        info_row = QHBoxLayout()
        self.lbl_a = QLabel("A: —")
        self.lbl_b = QLabel("B: —")
        self.lbl_count = QLabel("")
        for lbl in [self.lbl_a, self.lbl_b, self.lbl_count]:
            lbl.setStyleSheet("color: #3d5068; font-size: 11px; font-family: Consolas;")
        info_row.addWidget(self.lbl_a)
        info_row.addWidget(QLabel(" │ "))
        info_row.addWidget(self.lbl_b)
        info_row.addStretch()
        info_row.addWidget(self.lbl_count)
        root.addLayout(info_row)

        # Diff table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Address", "Region", "ROM A", "ROM B", "Delta"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 90)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 70)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 70)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 70)
        self.table.setFont(QFont("Consolas", 10))
        self.table.setAlternatingRowColors(False)
        root.addWidget(self.table)

    # ── Load ──────────────────────────────────────────────────────────────────

    def _load_rom(self, slot: str):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Open ROM {slot.upper()}", "", "BIN Files (*.bin *.BIN);;All Files (*)"
        )
        if not path:
            return
        with open(path, "rb") as f:
            data = f.read()
        if len(data) != 0x8000:
            return

        result = detect_rom(data)
        if slot == "a":
            self._rom_a = data
            self._res_a = result
            self.lbl_a.setText(f"A: {result.label}  [{result.crc32:#010x}]")
        else:
            self._rom_b = data
            self._res_b = result
            self.lbl_b.setText(f"B: {result.label}  [{result.crc32:#010x}]")

        self.btn_diff.setEnabled(self._rom_a is not None and self._rom_b is not None)

    # ── Diff ──────────────────────────────────────────────────────────────────

    def _region_for(self, addr_abs: int, result: DetectionResult | None) -> str:
        if result is None:
            return ""
        for md in result.maps:
            end = md.data_addr + md.size - 1
            if md.data_addr <= addr_abs <= end:
                return md.name
        return ""

    def _run_diff(self):
        if not self._rom_a or not self._rom_b:
            return

        self.table.setRowCount(0)
        diffs = []
        base  = 0x0000   # ECU address = file offset directly (ROM mapped 1:1)

        for i in range(min(len(self._rom_a), len(self._rom_b))):
            ba = self._rom_a[i]
            bb = self._rom_b[i]
            if ba != bb:
                addr_abs = base + i
                region = self._region_for(addr_abs, self._res_a)
                diffs.append((addr_abs, region, ba, bb, bb - ba))

        self.lbl_count.setText(f"{len(diffs)} differences")
        self.table.setRowCount(len(diffs))

        for row, (addr, region, va, vb, delta) in enumerate(diffs):
            cells = [
                f"0x{addr:04X}",
                region or "—",
                f"{va:02X}  ({va})",
                f"{vb:02X}  ({vb})",
                f"{delta:+d}",
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                if col == 4:
                    color = QColor("#2dff6e") if delta > 0 else QColor("#ff4444")
                    item.setForeground(QBrush(color))
                self.table.setItem(row, col, item)

    # ── Called from main when primary ROM is loaded ───────────────────────────

    def set_rom_a(self, result: DetectionResult, rom: bytes):
        """Pre-populate ROM A from the currently loaded ROM."""
        self._rom_a = rom
        self._res_a = result
        self.lbl_a.setText(f"A: {result.label}  [{result.crc32:#010x}]")
        self.btn_diff.setEnabled(self._rom_b is not None)
