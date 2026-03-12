"""
ui/overview_tab.py
ROM overview — variant, type, rev limit, code flags, checksum status.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QFileDialog, QSizePolicy, QFrame,
    QSpinBox, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from digitool.rom_profiles import (
    DetectionResult, VARIANT_LABELS, CODE_PATCHES,
    compute_checksum, KNOWN_CRCS, rpm_to_rev_limit
)


def _badge(text: str, color: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; background: transparent; "
        f"border: 1px solid {color}; padding: 2px 8px; font-size: 11px; "
        f"letter-spacing: 1px;"
    )
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFixedHeight(22)
    return lbl


class OverviewTab(QWidget):
    """
    Shows loaded ROM summary: variant, family, rev limit,
    code flags, checksum validity. Also hosts the Open / Save buttons.
    """

    sig_open_rom  = pyqtSignal()
    sig_save_rom  = pyqtSignal()
    sig_save_as   = pyqtSignal()
    sig_rom_mutated = pyqtSignal(object)   # emitted when rev limit or patches written in-place

    def __init__(self, parent=None):
        super().__init__(parent)
        self._result: DetectionResult | None = None
        self._rom:    bytes | None = None
        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # ── Title ────────────────────────────────────────────────────────────
        title = QLabel("ROM Overview")
        title.setObjectName("lbl_title")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        root.addWidget(title)

        # ── File actions ─────────────────────────────────────────────────────
        grp_file = QGroupBox("File")
        fl = QHBoxLayout(grp_file)
        self.btn_open = QPushButton("⊕  Open ROM (.BIN)")
        self.btn_open.setObjectName("btn_open")
        self.btn_open.clicked.connect(self.sig_open_rom)
        self.btn_save = QPushButton("↓  Save ROM")
        self.btn_save.setObjectName("btn_save")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.sig_save_rom)
        self.btn_save_as = QPushButton("↓  Save As…")
        self.btn_save_as.setEnabled(False)
        self.btn_save_as.clicked.connect(self.sig_save_as)
        fl.addWidget(self.btn_open)
        fl.addWidget(self.btn_save)
        fl.addWidget(self.btn_save_as)
        fl.addStretch()
        root.addWidget(grp_file)

        # ── Variant info ─────────────────────────────────────────────────────
        grp_var = QGroupBox("Variant")
        vl = QVBoxLayout(grp_var)

        self.lbl_variant  = QLabel("—")
        self.lbl_variant.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.lbl_variant.setStyleSheet("color: #00d4ff;")

        self.lbl_family   = QLabel("—")
        self.lbl_cal      = QLabel("—")
        self.lbl_conf     = QLabel("—")
        self.lbl_crc      = QLabel("—")
        self.lbl_crc.setStyleSheet("color: #3d5068; font-family: Consolas; font-size: 11px;")

        for lbl, prefix in [
            (self.lbl_family, "Map Family:"),
            (self.lbl_cal,    "Calibration:"),
            (self.lbl_conf,   "Confidence:"),
        ]:
            row = QHBoxLayout()
            pl = QLabel(prefix)
            pl.setFixedWidth(110)
            pl.setStyleSheet("color: #3d5068; font-size: 11px;")
            row.addWidget(pl)
            row.addWidget(lbl)
            row.addStretch()
            vl.addLayout(row)

        vl.addWidget(self.lbl_variant)
        vl.addWidget(self.lbl_crc)
        root.addWidget(grp_var)

        # ── Rev limit ────────────────────────────────────────────────────────
        grp_rev = QGroupBox("Rev Limit")
        rl = QHBoxLayout(grp_rev)
        self.lbl_rev = QLabel("— RPM")
        self.lbl_rev.setFont(QFont("Consolas", 14))
        self.lbl_rev.setStyleSheet("color: #e8b84b;")

        self.spin_rev = QSpinBox()
        self.spin_rev.setRange(1000, 9000)
        self.spin_rev.setSingleStep(50)
        self.spin_rev.setSuffix(" RPM")
        self.spin_rev.setEnabled(False)
        self.spin_rev.setFixedWidth(140)
        self.spin_rev.setStyleSheet(
            "QSpinBox { background: #111820; color: #e8b84b; border: 1px solid #e8b84b; "
            "padding: 4px 8px; font-family: Consolas; font-size: 13px; }"
            "QSpinBox:disabled { border-color: #1a2332; color: #3d5068; }"
            "QSpinBox::up-button, QSpinBox::down-button { width: 18px; background: #1a2332; }"
        )
        self.btn_apply_rev = QPushButton("Apply")
        self.btn_apply_rev.setEnabled(False)
        self.btn_apply_rev.setFixedWidth(80)
        self.btn_apply_rev.clicked.connect(self._apply_rev_limit)
        self.lbl_rev_hint = QLabel("Edit and click Apply to write to ROM")
        self.lbl_rev_hint.setStyleSheet("color: #3d5068; font-size: 10px;")

        rl.addWidget(self.lbl_rev)
        rl.addSpacing(20)
        rl.addWidget(self.spin_rev)
        rl.addWidget(self.btn_apply_rev)
        rl.addSpacing(12)
        rl.addWidget(self.lbl_rev_hint)
        rl.addStretch()
        root.addWidget(grp_rev)

        # ── Checksum ─────────────────────────────────────────────────────────
        grp_cs = QGroupBox("Checksum")
        cl = QHBoxLayout(grp_cs)
        self.badge_cs = _badge("NO ROM", "#3d5068")
        cl.addWidget(self.badge_cs)
        cl.addStretch()
        root.addWidget(grp_cs)

        # ── Code flags ───────────────────────────────────────────────────────
        grp_flags = QGroupBox("Code Patches")
        self.flags_layout = QVBoxLayout(grp_flags)
        self._flag_badges: dict = {}
        for key, p in CODE_PATCHES.items():
            row = QHBoxLayout()
            name_lbl = QLabel(p["label"])
            name_lbl.setFixedWidth(180)
            name_lbl.setStyleSheet("color: #3d5068; font-size: 11px;")
            badge = _badge("—", "#3d5068")
            badge.setFixedWidth(80)
            self._flag_badges[key] = badge
            row.addWidget(name_lbl)
            row.addWidget(badge)
            row.addStretch()
            self.flags_layout.addLayout(row)
        root.addWidget(grp_flags)

        root.addStretch()

    # ── Public API ────────────────────────────────────────────────────────────

    def update_rom(self, result: DetectionResult, rom: bytes):
        self._result = result
        self._rom    = rom

        self.lbl_variant.setText(result.label)
        self.lbl_family.setText(result.family)
        self.lbl_cal.setText(result.cal if result.cal else "UNKNOWN")
        self.lbl_conf.setText(result.confidence)
        self.lbl_crc.setText(f"CRC32: {result.crc32:#010x}")

        # Cal colour
        cal_color = "#2dff6e" if result.is_known_stock else "#e8b84b"
        self.lbl_cal.setStyleSheet(f"color: {cal_color};")

        # Rev limit
        rpm = result.rev_limit_rpm(rom)
        self.lbl_rev.setText(f"{rpm:,} RPM" if rpm else "Unknown")
        if rpm and result.rev_addr is not None:
            self.spin_rev.blockSignals(True)
            self.spin_rev.setValue(rpm)
            self.spin_rev.blockSignals(False)
            self.spin_rev.setEnabled(True)
            self.btn_apply_rev.setEnabled(True)
        else:
            self.spin_rev.setEnabled(False)
            self.btn_apply_rev.setEnabled(False)

        # Checksum
        crc = compute_checksum(rom)
        is_known = crc in KNOWN_CRCS
        if is_known:
            self._set_badge(self.badge_cs, "VERIFIED", "#2dff6e")
        else:
            self._set_badge(self.badge_cs, "MODIFIED", "#e8b84b")

        # Code flags
        flags = result.code_flags(rom)
        for key, badge in self._flag_badges.items():
            if key not in flags:
                self._set_badge(badge, "N/A", "#3d5068")
            elif flags[key]:
                self._set_badge(badge, "PATCHED", "#e8b84b")
            else:
                self._set_badge(badge, "STOCK", "#2dff6e")

        self.btn_save.setEnabled(True)
        self.btn_save_as.setEnabled(True)

    def clear(self):
        self._result = None
        self._rom    = None
        self.lbl_variant.setText("—")
        self.lbl_family.setText("—")
        self.lbl_cal.setText("—")
        self.lbl_conf.setText("—")
        self.lbl_crc.setText("—")
        self.lbl_rev.setText("— RPM")
        self.spin_rev.setEnabled(False)
        self.btn_apply_rev.setEnabled(False)
        self._set_badge(self.badge_cs, "NO ROM", "#3d5068")
        for badge in self._flag_badges.values():
            self._set_badge(badge, "—", "#3d5068")
        self.btn_save.setEnabled(False)
        self.btn_save_as.setEnabled(False)

    def _apply_rev_limit(self):
        """Write new rev limit to ROM bytearray and refresh display."""
        if self._result is None or self._rom is None:
            return
        if self._result.rev_addr is None:
            return
        new_rpm = self.spin_rev.value()
        raw16   = rpm_to_rev_limit(new_rpm)
        addr    = self._result.rev_addr - 0x4000   # ROM base offset
        if isinstance(self._rom, (bytes, bytearray)):
            rom_ba = bytearray(self._rom)
            rom_ba[addr]     = (raw16 >> 8) & 0xFF
            rom_ba[addr + 1] = raw16 & 0xFF
            self._rom = bytes(rom_ba)
        actual_rpm = round(30_000_000 / raw16) if raw16 else 0
        self.lbl_rev.setText(f"{actual_rpm:,} RPM")
        self.lbl_rev_hint.setText(
            f"Written 0x{raw16:04X} @ 0x{self._result.rev_addr:04X} — save ROM to persist"
        )
        self.lbl_rev_hint.setStyleSheet("color: #2dff6e; font-size: 10px;")
        # Propagate back to main window via signal so save includes this edit
        self.sig_rom_mutated.emit(self._rom)



    @staticmethod
    def _set_badge(badge: QLabel, text: str, color: str):
        badge.setText(text)
        badge.setStyleSheet(
            f"color: {color}; background: transparent; "
            f"border: 1px solid {color}; padding: 2px 8px; font-size: 11px; "
            f"letter-spacing: 1px;"
        )
