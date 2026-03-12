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
    compute_checksum, KNOWN_CRCS, rpm_to_rev_limit, detect_map_sensor
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

    sig_open_rom    = pyqtSignal()
    sig_save_rom    = pyqtSignal()
    sig_save_as     = pyqtSignal()
    sig_save_512    = pyqtSignal()          # export 64 KB mirrored for 27C512
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
        self.btn_save = QPushButton("↓  Save 27C256  (32 KB)")
        self.btn_save.setObjectName("btn_save")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.sig_save_rom)
        self.btn_save_as = QPushButton("↓  Save As…")
        self.btn_save_as.setEnabled(False)
        self.btn_save_as.clicked.connect(self.sig_save_as)

        self.btn_save_512 = QPushButton("↓  Save 27C512  (64 KB mirrored)")
        self.btn_save_512.setObjectName("btn_save_512")
        self.btn_save_512.setEnabled(False)
        self.btn_save_512.setToolTip(
            "Writes the 32 KB ROM twice (mirrored) into a 64 KB file.\n"
            "Required for burning to a 27C512 EPROM.\n"
            "The ECU reads the upper half; both halves are identical."
        )
        self.btn_save_512.clicked.connect(self.sig_save_512)

        fl.addWidget(self.btn_open)
        fl.addWidget(self.btn_save)
        fl.addWidget(self.btn_save_as)
        fl.addSpacing(16)
        fl.addWidget(self.btn_save_512)
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

        # ── MAP Sensor ───────────────────────────────────────────────────────
        grp_sensor = QGroupBox("MAP Sensor")
        sl = QHBoxLayout(grp_sensor)
        self.badge_sensor = _badge("NO ROM", "#3d5068")
        sl.addWidget(self.badge_sensor)
        self.lbl_sensor_method = QLabel("")
        self.lbl_sensor_method.setStyleSheet("color: #3d5068; font-size: 11px;")
        sl.addWidget(self.lbl_sensor_method)
        sl.addStretch()
        root.addWidget(grp_sensor)

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

        # ── Map address table (collapsible) ──────────────────────────────────
        from PyQt5.QtWidgets import QPlainTextEdit
        grp_maps = QGroupBox("Map Verification")
        ml = QVBoxLayout(grp_maps)
        ml.setSpacing(4)

        # Toggle button row
        map_hdr = QHBoxLayout()
        self.lbl_map_summary = QLabel("No ROM loaded")
        self.lbl_map_summary.setStyleSheet("color: #3d5068; font-size: 11px; font-family: Consolas;")
        self.btn_map_toggle = QPushButton("Map Addresses ▼")
        self.btn_map_toggle.setFlat(True)
        self.btn_map_toggle.setCheckable(True)
        self.btn_map_toggle.setChecked(False)
        self.btn_map_toggle.setStyleSheet(
            "QPushButton { color: #00d4ff; font-size: 11px; border: none; padding: 0; }"
            "QPushButton:hover { color: #bccdd8; }"
        )
        self.btn_map_toggle.toggled.connect(self._toggle_map_table)
        map_hdr.addWidget(self.lbl_map_summary)
        map_hdr.addStretch()
        map_hdr.addWidget(self.btn_map_toggle)
        ml.addLayout(map_hdr)

        # Monospaced table (hidden by default)
        self.wgt_map_table = QPlainTextEdit()
        self.wgt_map_table.setReadOnly(True)
        self.wgt_map_table.setMaximumHeight(220)
        self.wgt_map_table.setFont(QFont("Courier New", 10))
        self.wgt_map_table.setStyleSheet(
            "QPlainTextEdit { background: #0d1117; color: #bccdd8; "
            "border: 1px solid #1a2332; font-family: 'Courier New', monospace; }"
        )
        self.wgt_map_table.setVisible(False)
        ml.addWidget(self.wgt_map_table)
        root.addWidget(grp_maps)

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

        # MAP sensor range
        kpa = result.map_sensor_kpa
        _, sensor_method = detect_map_sensor(rom)
        if kpa == 250:
            self._set_badge(self.badge_sensor, "250 kPa", "#00d4ff")
        elif kpa == 200:
            self._set_badge(self.badge_sensor, "200 kPa", "#2dff6e")
        else:
            self._set_badge(self.badge_sensor, f"{kpa} kPa", "#e8b84b")
        self.lbl_sensor_method.setText(sensor_method)

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
        self.btn_save_512.setEnabled(True)

        # Map address table
        self._build_map_table(result, rom)

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
        self._set_badge(self.badge_sensor, "NO ROM", "#3d5068")
        self.lbl_sensor_method.setText("")
        for badge in self._flag_badges.values():
            self._set_badge(badge, "—", "#3d5068")
        self.btn_save.setEnabled(False)
        self.btn_save_as.setEnabled(False)
        self.btn_save_512.setEnabled(False)
        self.lbl_map_summary.setText("No ROM loaded")
        self.wgt_map_table.setPlainText("")

    def _toggle_map_table(self, checked: bool):
        self.wgt_map_table.setVisible(checked)
        self.btn_map_toggle.setText("Map Addresses ▲" if checked else "Map Addresses ▼")

    def _build_map_table(self, result: DetectionResult, rom: bytes):
        """Build the map address verification table and update summary label."""
        maps = result.maps
        if not maps:
            self.lbl_map_summary.setText("No map definitions for this variant")
            self.wgt_map_table.setPlainText("")
            return

        # Count maps that read non-fill data (first byte != 0x41 fill)
        ok_count = 0
        for m in maps:
            try:
                first = rom[m.data_addr]
                if first != 0x41:
                    ok_count += 1
            except IndexError:
                pass

        total = len(maps)
        summary_color = "#2dff6e" if ok_count == total else "#e8b84b"
        self.lbl_map_summary.setText(
            f"{ok_count}/{total} maps verified  ·  {result.family}  ·  {total} entries"
        )
        self.lbl_map_summary.setStyleSheet(
            f"color: {summary_color}; font-size: 11px; font-family: Consolas;"
        )

        # Build table text — matches reference app style
        lines = [
            f"  {'MAP NAME':<32}  {'DATA':>6}  {'END':>6}  {'SZ':>5}  TYPE   STATUS",
            "  " + "─" * 72,
        ]
        for m in maps:
            end_addr  = m.data_addr + m.size - 1
            map_type  = f"{m.rows}×{m.cols}" if m.rows > 1 else f"1×{m.cols}"
            try:
                first = rom[m.data_addr]
                status = "OK" if first != 0x41 else "FILL?"
                s_color = "✓" if first != 0x41 else "?"
            except IndexError:
                status = "OOB"
                s_color = "!"
            lines.append(
                f"  {m.name:<32}  0x{m.data_addr:04X}  0x{end_addr:04X}  "
                f"{m.size:>4}B  {map_type:<6}  {s_color} {status}"
            )

        # Rev limit line
        if result.rev_addr:
            try:
                hi  = rom[result.rev_addr]
                lo  = rom[result.rev_addr + 1]
                val = (hi << 8) | lo
                rpm = round(30_000_000 / val) if val else 0
                lines.append("  " + "─" * 72)
                lines.append(
                    f"  {'Rev Limit':<32}  0x{result.rev_addr:04X}  0x{result.rev_addr+1:04X}"
                    f"     2B  16-bit   ✓ {rpm:,} RPM  (0x{val:04X})"
                )
            except Exception:
                pass

        self.wgt_map_table.setPlainText("\n".join(lines))

    def _apply_rev_limit(self):
        """Write new rev limit to ROM bytearray and refresh display."""
        if self._result is None or self._rom is None:
            return
        if self._result.rev_addr is None:
            return
        new_rpm = self.spin_rev.value()
        raw16   = rpm_to_rev_limit(new_rpm)
        addr    = self._result.rev_addr   # ECU address = file offset directly
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
