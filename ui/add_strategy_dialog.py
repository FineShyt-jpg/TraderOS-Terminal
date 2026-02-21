"""
Add / Edit Strategy Variant Dialog

Allows user to manually register a strategy with its parameter fingerprint.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton,
    QGroupBox, QDialogButtonBox, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt

from core.strategy_fingerprint import StrategyParams


class AddStrategyDialog(QDialog):
    """
    Dialog for adding or editing a strategy parameter set.
    """

    def __init__(self, params: StrategyParams = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Strategy Variant" if params is None else "Edit Strategy Variant")
        self.setMinimumWidth(480)
        self.setObjectName("addStrategyDialog")
        self._params = params
        self._setup_ui()
        if params:
            self._populate(params)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Identity
        identity_group = QGroupBox("Strategy Identity")
        ig_layout = QGridLayout(identity_group)
        ig_layout.addWidget(QLabel("Label (NT8 strategy name):"), 0, 0)
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("e.g. MuddyWaterV4")
        ig_layout.addWidget(self.label_edit, 0, 1)

        ig_layout.addWidget(QLabel("Account:"), 1, 0)
        self.account_edit = QLineEdit()
        self.account_edit.setPlaceholderText("e.g. SimHouse 3")
        ig_layout.addWidget(self.account_edit, 1, 1)
        layout.addWidget(identity_group)

        # Smoothness / ADX
        adx_group = QGroupBox("Smoothness Filter")
        adx_layout = QHBoxLayout(adx_group)
        self.adx_on = QCheckBox("ADX Filter Enabled")
        adx_layout.addWidget(self.adx_on)
        adx_layout.addWidget(QLabel("Period:"))
        self.adx_spin = QSpinBox()
        self.adx_spin.setRange(1, 200)
        self.adx_spin.setValue(14)
        self.adx_spin.setEnabled(False)
        adx_layout.addWidget(self.adx_spin)
        adx_layout.addStretch()
        self.adx_on.toggled.connect(self.adx_spin.setEnabled)
        layout.addWidget(adx_group)

        # Protective Stop
        ps_group = QGroupBox("Protective Stop")
        ps_layout = QHBoxLayout(ps_group)
        self.ps_on = QCheckBox("Protective Stop Enabled")
        ps_layout.addWidget(self.ps_on)
        ps_layout.addWidget(QLabel("Ticks:"))
        self.ps_spin = QSpinBox()
        self.ps_spin.setRange(1, 10000)
        self.ps_spin.setValue(100)
        self.ps_spin.setEnabled(False)
        ps_layout.addWidget(self.ps_spin)
        ps_layout.addStretch()
        self.ps_on.toggled.connect(self.ps_spin.setEnabled)
        layout.addWidget(ps_group)

        # Failed Signal Exit
        fs_group = QGroupBox("Failed Signal Exit")
        fs_layout = QGridLayout(fs_group)
        self.fs_on = QCheckBox("Failed Signal Exit Enabled")
        fs_layout.addWidget(self.fs_on, 0, 0, 1, 4)
        fs_layout.addWidget(QLabel("Long Failed Exit SMI:"), 1, 0)
        self.lf_spin = QDoubleSpinBox()
        self.lf_spin.setRange(-200, 200)
        self.lf_spin.setValue(-75)
        self.lf_spin.setEnabled(False)
        fs_layout.addWidget(self.lf_spin, 1, 1)
        fs_layout.addWidget(QLabel("Short Failed Exit SMI:"), 1, 2)
        self.sf_spin = QDoubleSpinBox()
        self.sf_spin.setRange(-200, 200)
        self.sf_spin.setValue(75)
        self.sf_spin.setEnabled(False)
        fs_layout.addWidget(self.sf_spin, 1, 3)
        self.fs_on.toggled.connect(self.lf_spin.setEnabled)
        self.fs_on.toggled.connect(self.sf_spin.setEnabled)
        layout.addWidget(fs_group)

        # Thresholds
        th_group = QGroupBox("Entry / Exit Thresholds")
        th_layout = QGridLayout(th_group)

        th_layout.addWidget(QLabel("Overbought:"), 0, 0)
        self.ob_spin = QDoubleSpinBox()
        self.ob_spin.setRange(-500, 500)
        self.ob_spin.setValue(70)
        th_layout.addWidget(self.ob_spin, 0, 1)

        th_layout.addWidget(QLabel("Oversold:"), 0, 2)
        self.os_spin = QDoubleSpinBox()
        self.os_spin.setRange(-500, 500)
        self.os_spin.setValue(-70)
        th_layout.addWidget(self.os_spin, 0, 3)

        th_layout.addWidget(QLabel("Long Exit At:"), 1, 0)
        self.le_spin = QDoubleSpinBox()
        self.le_spin.setRange(-500, 500)
        self.le_spin.setValue(30)
        th_layout.addWidget(self.le_spin, 1, 1)

        th_layout.addWidget(QLabel("Short Exit At:"), 1, 2)
        self.se_spin = QDoubleSpinBox()
        self.se_spin.setRange(-500, 500)
        self.se_spin.setValue(-30)
        th_layout.addWidget(self.se_spin, 1, 3)

        layout.addWidget(th_group)

        # Notes
        layout.addWidget(QLabel("Notes (optional):"))
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("e.g. Tighter stop, aggressive entries")
        layout.addWidget(self.notes_edit)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, p: StrategyParams):
        self.label_edit.setText(p.label or "")
        self.account_edit.setText(p.account or "")

        if p.adx_period is not None:
            self.adx_on.setChecked(True)
            self.adx_spin.setValue(p.adx_period)

        if p.protective_stop_ticks is not None:
            self.ps_on.setChecked(True)
            self.ps_spin.setValue(p.protective_stop_ticks)

        if p.long_failed_exit is not None or p.short_failed_exit is not None:
            self.fs_on.setChecked(True)
            if p.long_failed_exit is not None:
                self.lf_spin.setValue(p.long_failed_exit)
            if p.short_failed_exit is not None:
                self.sf_spin.setValue(p.short_failed_exit)

        if p.overbought is not None:
            self.ob_spin.setValue(p.overbought)
        if p.oversold is not None:
            self.os_spin.setValue(p.oversold)
        if p.long_exit_at is not None:
            self.le_spin.setValue(p.long_exit_at)
        if p.short_exit_at is not None:
            self.se_spin.setValue(p.short_exit_at)

        self.notes_edit.setText(p.notes or "")

    def _accept(self):
        label = self.label_edit.text().strip()
        account = self.account_edit.text().strip()

        if not label or not account:
            QMessageBox.warning(self, "Required", "Label and Account are required.")
            return

        self.accept()

    def get_params(self) -> StrategyParams:
        return StrategyParams(
            label=self.label_edit.text().strip(),
            account=self.account_edit.text().strip(),
            adx_period=self.adx_spin.value() if self.adx_on.isChecked() else None,
            protective_stop_ticks=self.ps_spin.value() if self.ps_on.isChecked() else None,
            long_failed_exit=self.lf_spin.value() if self.fs_on.isChecked() else None,
            short_failed_exit=self.sf_spin.value() if self.fs_on.isChecked() else None,
            overbought=self.ob_spin.value(),
            oversold=self.os_spin.value(),
            long_exit_at=self.le_spin.value(),
            short_exit_at=self.se_spin.value(),
            notes=self.notes_edit.text().strip(),
        )
