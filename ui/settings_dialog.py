"""
Settings Dialog

Configure:
 - NT8 database path
 - Output directory
 - Anthropic API key
 - Refresh interval
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QDialogButtonBox,
    QGroupBox, QFileDialog, QCheckBox
)
from PyQt6.QtCore import Qt


class SettingsDialog(QDialog):

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        self.setObjectName("settingsDialog")
        self.config = config.copy()
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # NT8 Database
        nt8_group = QGroupBox("NinjaTrader 8")
        nt8_layout = QGridLayout(nt8_group)

        nt8_layout.addWidget(QLabel("Database Path (trade.sqlite):"), 0, 0)
        self.db_path_edit = QLineEdit()
        nt8_layout.addWidget(self.db_path_edit, 0, 1)
        btn_browse_db = QPushButton("Browse")
        btn_browse_db.clicked.connect(self._browse_db)
        nt8_layout.addWidget(btn_browse_db, 0, 2)

        nt8_layout.addWidget(QLabel("Workspaces Path:"), 1, 0)
        self.ws_path_edit = QLineEdit()
        nt8_layout.addWidget(self.ws_path_edit, 1, 1)
        btn_browse_ws = QPushButton("Browse")
        btn_browse_ws.clicked.connect(self._browse_ws)
        nt8_layout.addWidget(btn_browse_ws, 1, 2)

        nt8_layout.addWidget(QLabel("Auto-refresh interval (seconds):"), 2, 0)
        self.refresh_spin = QSpinBox()
        self.refresh_spin.setRange(1, 300)
        self.refresh_spin.setValue(5)
        nt8_layout.addWidget(self.refresh_spin, 2, 1)

        layout.addWidget(nt8_group)

        # Output Directory
        out_group = QGroupBox("Output")
        out_layout = QHBoxLayout(out_group)
        out_layout.addWidget(QLabel("Output Directory:"))
        self.output_edit = QLineEdit()
        out_layout.addWidget(self.output_edit)
        btn_browse_out = QPushButton("Browse")
        btn_browse_out.clicked.connect(self._browse_output)
        out_layout.addWidget(btn_browse_out)
        layout.addWidget(out_group)

        # Claude API
        api_group = QGroupBox("Claude AI (Anthropic)")
        api_layout = QGridLayout(api_group)

        api_layout.addWidget(QLabel("API Key:"), 0, 0)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("sk-ant-...")
        api_layout.addWidget(self.api_key_edit, 0, 1)

        self.show_key_cb = QCheckBox("Show key")
        self.show_key_cb.toggled.connect(
            lambda v: self.api_key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if v else QLineEdit.EchoMode.Password
            )
        )
        api_layout.addWidget(self.show_key_cb, 0, 2)

        api_layout.addWidget(QLabel("Model:"), 1, 0)
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("claude-sonnet-4-5")
        api_layout.addWidget(self.model_edit, 1, 1)

        layout.addWidget(api_group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_config(self):
        self.db_path_edit.setText(self.config.get("nt8_db_path", ""))
        self.ws_path_edit.setText(self.config.get("nt8_workspaces_path", ""))
        self.output_edit.setText(self.config.get("output_dir", ""))
        self.api_key_edit.setText(self.config.get("api_key", ""))
        self.model_edit.setText(self.config.get("model", "claude-sonnet-4-5"))
        self.refresh_spin.setValue(self.config.get("refresh_interval", 5))

    def _browse_db(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select NT8 trade.sqlite", "", "SQLite Files (*.sqlite *.db)"
        )
        if path:
            self.db_path_edit.setText(path)

    def _browse_ws(self):
        path = QFileDialog.getExistingDirectory(self, "Select NT8 Workspaces Folder")
        if path:
            self.ws_path_edit.setText(path)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self.output_edit.setText(path)

    def _save(self):
        self.config["nt8_db_path"] = self.db_path_edit.text().strip()
        self.config["nt8_workspaces_path"] = self.ws_path_edit.text().strip()
        self.config["output_dir"] = self.output_edit.text().strip()
        self.config["api_key"] = self.api_key_edit.text().strip()
        self.config["model"] = self.model_edit.text().strip() or "claude-sonnet-4-5"
        self.config["refresh_interval"] = self.refresh_spin.value()
        self.accept()

    def get_config(self) -> dict:
        return self.config
