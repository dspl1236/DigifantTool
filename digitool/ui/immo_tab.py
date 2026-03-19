"""
ui/immo_tab.py
Immobilizer bypass tab — Digifant 3 ECUs (ABF / ABA / 9A).

Shows patch status for the loaded ROM, workflow notes for locating
the patch address via Ghidra disassembly, and a guarded apply button
that is only enabled when a patch is CONFIRMED with verified bytes.

For all other variants (Digi 1, DF2) the tab displays an informational
placeholder so it's never confusingly blank.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QTextEdit, QSizePolicy,
    QScrollArea, QFrame,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from digitool.rom_profiles import (
    DetectionResult,
    VARIANT_DF3_ABF, VARIANT_DF3_ABA, VARIANT_DF3_9A,
    VARIANT_DF2_2E, VARIANT_DF2_PF,
)
from digitool.immo_patches import (
    PATCH_DB, ImmoPatch, ImmoPatchError,
    find_patches_for_ecu,
    verify_patch_location, apply_patch, check_already_patched,
)

_DF3_VARIANTS = {VARIANT_DF3_ABF, VARIANT_DF3_ABA, VARIANT_DF3_9A}

_PALETTE = {
    "CONFIRMED":   "#4ec97b",   # green
    "PROVISIONAL": "#f0c060",   # amber
    "UNCONFIRMED": "#c06060",   # muted red
    "APPLIED":     "#4ec97b",
    "NOT_APPLIED":  "#bccdd8",
    "WRONG_BYTES":  "#e06060",
    "UNKNOWN":     "#888",
}

_GHIDRA_WORKFLOW_ABF = """\
Finding the ABF immo bypass address — Ghidra 8051 workflow
===========================================================

Prerequisites
  • Ghidra 11.x with the 8051 processor plugin (included in base install)
  • 32KB ROM binary (or upper half of 64KB chip read)

Steps

1. Import ROM
   File → Import File → select .BIN
   Language: 8051 / 8051 / default / little-endian
   Click OK, then double-click to open in CodeBrowser.

2. Let auto-analysis run
   Analysis → Auto Analyze → accept defaults → Analyze.
   The disassembler will follow LJMP from 0x0000 and trace the reset path.

3. Find the startup/immo check subroutine
   In the Listing view, navigate to address 0x0000.
   You will see:   LJMP  0xXXXX   (the reset target)
   Follow that jump. Look for a short subroutine (< 50 instructions) that:
     a) Reads an external port bit (MOV A, P1 / MOV A, P3 / ORL A,...)
     b) Calls or branches to a flag-setting routine
     c) Ends by returning (RET) or jumping to the main loop

4. Identify the conditional jump
   Immediately after the immo-check call, look for:
     JZ   offset   (opcode 0x60) — "jump if flag clear (immo not seen)"
     JNZ  offset   (opcode 0x70) — "jump if flag set (immo seen)"
   One of these branches to a no-injection path (e.g. SJMP to an infinite loop).

5. Record the address
   Note the hex address of the JZ or JNZ instruction.
   Note the 2 bytes at that address (opcode + offset).

6. Verify
   In the ROM hex dump, confirm those exact 2 bytes at that offset.
   Update PATCH_DB in immo_patches.py:
     patch_addr = <your address>
     original   = bytes([<opcode>, <offset>])
     patched    = bytes([0x00, 0x00])   # NOP NOP (8051 NOP = 0x00)
     confidence = "CONFIRMED"

7. Apply via DigiTool Immo tab
   Reload the ROM. Verify button will confirm bytes. Apply button will patch.
   Save as new file. Bench-test on ECU before driving.

Notes
  • NOP in 8051 = 0x00 (one byte). The conditional jump is 2 bytes, so NOP×2.
  • Never burn a patched ROM without bench verification first.
  • ABA (HD6303 CPU): NOP = 0x01. Conditional branch = BEQ (0x27) or BNE (0x26).
    For ABA use Ghidra's 6800/6303 processor instead of 8051.
"""

_PLACEHOLDER_NO_IMMO = """\
No immobilizer on this variant.

Digi 1 (G60 / G40) and Digifant 2 (2E / PF) ECUs do not have an
immobilizer. This tab is only active for Digifant 3 variants:
  • ABF  2.0 16v  (Golf 3 GTI)
  • ABA  2.0 8v   (Golf 3 / Vento)
  • 9A   2.0 16v  (Corrado)

Load a DF3 ROM to see patch status and the Ghidra bypass workflow.
"""


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


class _PatchCard(QFrame):
    """One row per PATCH_DB entry — shows status, verify/apply controls."""

    sig_log = pyqtSignal(str)

    def __init__(self, patch: ImmoPatch, parent=None):
        super().__init__(parent)
        self._patch = patch
        self._rom: bytearray | None = None
        self._build()

    def _build(self):
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame { background: #1e2c38; border: 1px solid #2e4050; "
            "border-radius: 4px; }"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        # ── Header row ───────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        lbl_pn = QLabel(self._patch.ecu_pn)
        lbl_pn.setStyleSheet("color:#bccdd8; font-size:12px; font-weight:bold; border:none;")
        hdr.addWidget(lbl_pn)
        hdr.addStretch()
        conf_color = _PALETTE.get(self._patch.confidence, _PALETTE["UNKNOWN"])
        hdr.addWidget(_badge(self._patch.confidence, conf_color))
        lay.addLayout(hdr)

        # ── Description ──────────────────────────────────────────────────────
        lbl_desc = QLabel(self._patch.description)
        lbl_desc.setStyleSheet("color:#8ca8bc; font-size:11px; border:none;")
        lbl_desc.setWordWrap(True)
        lay.addWidget(lbl_desc)

        # ── Patch bytes ──────────────────────────────────────────────────────
        addr_str = f"0x{self._patch.patch_addr:04X}" if self._patch.confidence != "UNCONFIRMED" \
                   else "addr UNCONFIRMED"
        bytes_str = (
            f"addr: {addr_str}   "
            f"original: {self._patch.original.hex().upper()}   "
            f"patched: {self._patch.patched.hex().upper()}"
        )
        lbl_bytes = QLabel(bytes_str)
        lbl_bytes.setStyleSheet(
            "color:#6a8499; font-size:10px; font-family:Consolas,monospace; border:none;"
        )
        lay.addWidget(lbl_bytes)

        # ── Status + buttons ─────────────────────────────────────────────────
        ctl = QHBoxLayout()
        self._lbl_status = QLabel("Load a ROM to check status")
        self._lbl_status.setStyleSheet("color:#6a8499; font-size:11px; border:none;")
        ctl.addWidget(self._lbl_status)
        ctl.addStretch()

        self._btn_verify = QPushButton("Verify bytes")
        self._btn_verify.setEnabled(False)
        self._btn_verify.setFixedWidth(110)
        self._btn_verify.clicked.connect(self._verify)
        ctl.addWidget(self._btn_verify)

        self._btn_apply = QPushButton("Apply patch")
        self._btn_apply.setEnabled(False)
        self._btn_apply.setFixedWidth(110)
        self._btn_apply.setStyleSheet(
            "QPushButton:enabled { color: #1a2a35; background: #4ec97b; border:none; "
            "border-radius:3px; font-weight:bold; padding:4px 8px; } "
            "QPushButton:disabled { color:#3a5060; background:#1e2c38; border:1px solid #2e4050; "
            "border-radius:3px; padding:4px 8px; }"
        )
        self._btn_apply.clicked.connect(self._apply)
        ctl.addWidget(self._btn_apply)

        lay.addLayout(ctl)

        # Notes (collapsible would be nice; keep flat for now)
        if self._patch.notes:
            lbl_notes = QLabel(self._patch.notes)
            lbl_notes.setStyleSheet(
                "color:#5a7488; font-size:10px; font-family:Consolas,monospace; border:none;"
            )
            lbl_notes.setWordWrap(True)
            lay.addWidget(lbl_notes)

    # ── Public ────────────────────────────────────────────────────────────────

    def load_rom(self, rom: bytearray):
        self._rom = rom
        self._refresh_status()

    def get_rom(self) -> bytearray | None:
        return self._rom

    # ── Internal ──────────────────────────────────────────────────────────────

    def _refresh_status(self):
        if self._rom is None:
            self._lbl_status.setText("No ROM loaded")
            self._btn_verify.setEnabled(False)
            self._btn_apply.setEnabled(False)
            return

        self._btn_verify.setEnabled(True)

        if check_already_patched(bytes(self._rom), self._patch):
            self._lbl_status.setText("✓  Already patched")
            self._lbl_status.setStyleSheet(
                f"color:{_PALETTE['APPLIED']}; font-size:11px; border:none;"
            )
            self._btn_apply.setEnabled(False)
            return

        if self._patch.confidence == "UNCONFIRMED":
            self._lbl_status.setText("⚠  Address unconfirmed — do not apply")
            self._lbl_status.setStyleSheet(
                f"color:{_PALETTE['UNCONFIRMED']}; font-size:11px; border:none;"
            )
            self._btn_apply.setEnabled(False)
            return

        ok, msg = verify_patch_location(bytes(self._rom), self._patch)
        if ok:
            self._lbl_status.setText("✓  Bytes verified — ready to apply")
            self._lbl_status.setStyleSheet(
                f"color:{_PALETTE['CONFIRMED']}; font-size:11px; border:none;"
            )
            self._btn_apply.setEnabled(self._patch.confidence == "CONFIRMED")
        else:
            self._lbl_status.setText(f"✗  {msg}")
            self._lbl_status.setStyleSheet(
                f"color:{_PALETTE['WRONG_BYTES']}; font-size:11px; border:none;"
            )
            self._btn_apply.setEnabled(False)

    def _verify(self):
        if self._rom is None:
            return
        ok, msg = verify_patch_location(bytes(self._rom), self._patch)
        prefix = "✓" if ok else "✗"
        self.sig_log.emit(f"[{self._patch.ecu_pn}]  {prefix}  {msg}")
        self._refresh_status()

    def _apply(self):
        if self._rom is None:
            return
        try:
            self._rom, msg = apply_patch(self._rom, self._patch)
            self.sig_log.emit(f"[{self._patch.ecu_pn}]  {msg}")
            self._refresh_status()
        except ImmoPatchError as e:
            self.sig_log.emit(f"[{self._patch.ecu_pn}]  ERROR: {e}")


class ImmoTab(QWidget):
    """
    Immobilizer bypass tab.

    Active for DF3 variants; shows a placeholder for all others.
    Emits sig_rom_mutated when a patch is applied so main_window can
    offer a save prompt.
    """

    sig_rom_mutated = pyqtSignal(object)   # emits updated bytearray

    def __init__(self, parent=None):
        super().__init__(parent)
        self._result: DetectionResult | None = None
        self._rom:    bytearray | None = None
        self._cards:  list[_PatchCard] = []
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        title = QLabel("Immobilizer Bypass")
        title.setObjectName("lbl_title")
        title.setStyleSheet("font-size:18px; font-weight:bold; color:#bccdd8;")
        root.addWidget(title)

        sub = QLabel(
            "Digifant 3 (ABF / ABA / 9A) — bypass ROM patch for pre-immo engine swaps"
        )
        sub.setStyleSheet("color:#6a8499; font-size:11px;")
        root.addWidget(sub)

        # ── Status badge row ─────────────────────────────────────────────────
        badge_row = QHBoxLayout()
        self._badge_variant    = _badge("No ROM", "#6a8499")
        self._badge_immo_state = _badge("—", "#6a8499")
        badge_row.addWidget(self._badge_variant)
        badge_row.addWidget(self._badge_immo_state)
        badge_row.addStretch()
        root.addLayout(badge_row)

        # ── Main area (scrollable) ───────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self._scroll_inner = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_inner)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(10)

        # Placeholder shown when no DF3 ROM is loaded
        self._placeholder = QLabel(_PLACEHOLDER_NO_IMMO)
        self._placeholder.setStyleSheet(
            "color:#6a8499; font-size:11px; font-family:Consolas,monospace;"
        )
        self._placeholder.setWordWrap(True)
        self._scroll_layout.addWidget(self._placeholder)
        self._scroll_layout.addStretch()

        scroll.setWidget(self._scroll_inner)
        root.addWidget(scroll, stretch=3)

        # ── Ghidra workflow notes ────────────────────────────────────────────
        grp_ghidra = QGroupBox("Ghidra Disassembly Workflow")
        grp_ghidra.setStyleSheet(
            "QGroupBox { color:#8ca8bc; font-weight:bold; font-size:11px; "
            "border:1px solid #2e4050; border-radius:4px; margin-top:8px; } "
            "QGroupBox::title { subcontrol-origin:margin; left:8px; padding:0 4px; }"
        )
        g_lay = QVBoxLayout(grp_ghidra)
        self._txt_workflow = QTextEdit()
        self._txt_workflow.setReadOnly(True)
        self._txt_workflow.setPlainText(_GHIDRA_WORKFLOW_ABF)
        self._txt_workflow.setStyleSheet(
            "background:#111c24; color:#6a8499; font-size:10px; "
            "font-family:Consolas,monospace; border:none;"
        )
        self._txt_workflow.setFixedHeight(200)
        g_lay.addWidget(self._txt_workflow)
        root.addWidget(grp_ghidra)

        # ── Log output ───────────────────────────────────────────────────────
        grp_log = QGroupBox("Patch Log")
        grp_log.setStyleSheet(
            "QGroupBox { color:#8ca8bc; font-weight:bold; font-size:11px; "
            "border:1px solid #2e4050; border-radius:4px; margin-top:8px; } "
            "QGroupBox::title { subcontrol-origin:margin; left:8px; padding:0 4px; }"
        )
        g2_lay = QVBoxLayout(grp_log)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(90)
        self._log.setStyleSheet(
            "background:#111c24; color:#bccdd8; font-size:10px; "
            "font-family:Consolas,monospace; border:none;"
        )
        g2_lay.addWidget(self._log)
        root.addWidget(grp_log)

    # ── Public interface ──────────────────────────────────────────────────────

    def load_rom(self, result: DetectionResult, rom: bytearray):
        self._result = result
        self._rom    = bytearray(rom)
        self._rebuild_cards()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _rebuild_cards(self):
        # Remove old cards
        for card in self._cards:
            self._scroll_layout.removeWidget(card)
            card.setParent(None)
        self._cards.clear()

        # Remove stretch item at end
        while self._scroll_layout.count():
            item = self._scroll_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        if self._result is None or self._result.variant not in _DF3_VARIANTS:
            # Not a DF3 — show placeholder
            self._badge_variant.setText(
                self._result.variant if self._result else "No ROM"
            )
            self._badge_variant.setStyleSheet(
                "color:#6a8499; background:transparent; border:1px solid #6a8499; "
                "padding:2px 8px; font-size:11px; letter-spacing:1px;"
            )
            self._badge_immo_state.setText("No immobilizer")
            self._badge_immo_state.setStyleSheet(
                "color:#6a8499; background:transparent; border:1px solid #6a8499; "
                "padding:2px 8px; font-size:11px; letter-spacing:1px;"
            )
            placeholder = QLabel(_PLACEHOLDER_NO_IMMO)
            placeholder.setStyleSheet(
                "color:#6a8499; font-size:11px; font-family:Consolas,monospace;"
            )
            placeholder.setWordWrap(True)
            self._scroll_layout.addWidget(placeholder)
            self._scroll_layout.addStretch()
            return

        # DF3 variant loaded
        self._badge_variant.setText(self._result.variant)
        self._badge_variant.setStyleSheet(
            "color:#bccdd8; background:transparent; border:1px solid #bccdd8; "
            "padding:2px 8px; font-size:11px; letter-spacing:1px;"
        )

        # Collect relevant patches from PATCH_DB
        patches = find_patches_for_ecu(self._result.variant.split("_")[1])
        if not patches:
            # Try broader search
            patches = find_patches_for_ecu(self._result.variant)

        confirmed = [p for p in patches if p.confidence == "CONFIRMED"]
        unconf    = [p for p in patches if p.confidence != "CONFIRMED"]

        if confirmed:
            state_text  = f"{len(confirmed)} confirmed patch(es)"
            state_color = _PALETTE["CONFIRMED"]
        elif patches:
            state_text  = f"{len(patches)} patch(es) — addr unconfirmed"
            state_color = _PALETTE["UNCONFIRMED"]
        else:
            state_text  = "No patches in DB"
            state_color = _PALETTE["UNKNOWN"]

        self._badge_immo_state.setText(state_text)
        self._badge_immo_state.setStyleSheet(
            f"color:{state_color}; background:transparent; border:1px solid {state_color}; "
            "padding:2px 8px; font-size:11px; letter-spacing:1px;"
        )

        if patches:
            hdr = QLabel("Available patches")
            hdr.setStyleSheet("color:#8ca8bc; font-size:11px; font-weight:bold;")
            self._scroll_layout.addWidget(hdr)

            for patch in patches:
                card = _PatchCard(patch, self)
                card.sig_log.connect(self._append_log)
                if self._rom is not None:
                    card.load_rom(bytearray(self._rom))
                self._cards.append(card)
                self._scroll_layout.addWidget(card)
        else:
            lbl = QLabel(
                f"No patches found in PATCH_DB for {self._result.variant}.\n"
                "Submit ROM + disassembly to add entries."
            )
            lbl.setStyleSheet("color:#6a8499; font-size:11px;")
            lbl.setWordWrap(True)
            self._scroll_layout.addWidget(lbl)

        self._scroll_layout.addStretch()

    def _append_log(self, msg: str):
        self._log.append(msg)
        # Propagate mutated ROM upward
        for card in self._cards:
            rom = card.get_rom()
            if rom is not None:
                self._rom = rom
                self.sig_rom_mutated.emit(self._rom)
                break
