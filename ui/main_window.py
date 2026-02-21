"""
Main Window

Layout:
+-----------------------------------------------+
|  Menu Bar                      Status Bar      |
+-------------------+---------------------------+
|  Strategy Tree    |  Data Panel               |
|  (left)           |  (right)                  |
+-------------------+---------------------------+
|  [Tabs]                                        |
|  Claude Terminal  |  Research Browser          |
+-------------------+---------------------------+
"""

import json
import os
from pathlib import Path
from datetime import date
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QStatusBar, QMenuBar, QMenu, QMessageBox, QTabWidget,
    QLabel, QToolBar, QToolButton, QApplication, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QSettings
from PyQt6.QtGui import QAction, QKeySequence, QFont, QColor

from core.nt8_reader import NT8Reader
from core.strategy_fingerprint import StrategyRegistry, StrategyParams
from core.file_organizer import FileOrganizer
from core.claude_agent import ClaudeAgent
from core.data_watcher import NT8DataWatcher

from ui.strategy_tree_widget import StrategyTreeWidget
from ui.data_panel import DataPanel
from ui.claude_terminal import ClaudeTerminalWidget
from ui.browser_panel import BrowserPanel
from ui.add_strategy_dialog import AddStrategyDialog
from ui.settings_dialog import SettingsDialog


CONFIG_FILE = Path.home() / ".traderos" / "config.json"
DATA_DIR = Path.home() / ".traderos"


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TraderOS Terminal")
        self.setMinimumSize(1400, 900)

        # Load config
        self.config = self._load_config()

        # Core components
        self.reader = self._init_reader()
        self.registry = StrategyRegistry(DATA_DIR)
        self.organizer = FileOrganizer(self._get_output_dir())
        self.agent = self._init_agent()

        # Data watcher
        self.watcher = NT8DataWatcher(self.reader.get_db_path(), interval_ms=5000)
        self.watcher.data_changed.connect(self._on_nt8_data_changed)
        self.watcher.connection_changed.connect(self._on_connection_changed)
        self.watcher.start()

        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()
        self._restore_geometry()

        # Initial refresh
        QTimer.singleShot(500, self._refresh_all)

    # ── Config ──────────────────────────────────────────────────────────────

    def _load_config(self) -> dict:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        # Defaults
        return {
            "nt8_db_path": str(
                Path.home() / "Documents" / "NinjaTrader 8" / "db" / "trade.sqlite"
            ),
            "nt8_workspaces_path": str(
                Path.home() / "Documents" / "NinjaTrader 8" / "workspaces"
            ),
            "output_dir": str(Path.home() / "TraderOS" / "output"),
            "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
            "model": "claude-sonnet-4-5",
            "refresh_interval": 5,
        }

    def _save_config(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

    def _init_reader(self) -> NT8Reader:
        reader = NT8Reader()
        db_path = self.config.get("nt8_db_path", "")
        if db_path:
            reader.set_db_path(db_path)
        return reader

    def _init_agent(self) -> ClaudeAgent:
        agent = ClaudeAgent(
            self.registry,
            self.organizer,
            api_key=self.config.get("api_key", ""),
        )
        model = self.config.get("model", "claude-sonnet-4-5")
        if model:
            agent.model = model
        return agent

    def _get_output_dir(self) -> Path:
        path_str = self.config.get("output_dir", "")
        if path_str:
            return Path(path_str)
        return Path.home() / "TraderOS" / "output"

    # ── UI Setup ─────────────────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top: strategy tree + data panel
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.setObjectName("topSplitter")

        self.strategy_tree = StrategyTreeWidget(self.registry, self.organizer)
        self.strategy_tree.setMinimumWidth(280)
        self.strategy_tree.setMaximumWidth(480)
        self.strategy_tree.strategy_selected.connect(self._on_strategy_selected)
        self.strategy_tree.day_selected.connect(self._on_day_selected)
        self.strategy_tree.composite_selected.connect(self._on_composite_selected)
        self.strategy_tree.add_strategy_requested.connect(self._add_strategy)
        self.strategy_tree.remove_strategy_requested.connect(self._remove_strategy)
        top_splitter.addWidget(self.strategy_tree)

        self.data_panel = DataPanel(self.organizer, self.reader)
        self.data_panel.analysis_requested.connect(self._on_analysis_requested)
        top_splitter.addWidget(self.data_panel)
        top_splitter.setSizes([320, 900])

        main_layout.addWidget(top_splitter, stretch=60)

        # Bottom: Claude terminal + Research browser
        bottom_tabs = QTabWidget()
        bottom_tabs.setObjectName("bottomTabs")
        bottom_tabs.setTabPosition(QTabWidget.TabPosition.West)

        self.claude_terminal = ClaudeTerminalWidget(self.agent)
        bottom_tabs.addTab(self.claude_terminal, "🧠\nClaude\nTerminal")

        self.browser_panel = BrowserPanel()
        bottom_tabs.addTab(self.browser_panel, "🌐\nResearch\nBrowser")

        main_layout.addWidget(bottom_tabs, stretch=40)

    def _make_action(self, text: str, slot, shortcut: str = None) -> QAction:
        """Create a QAction with optional shortcut - compatible with Qt 6.10+."""
        action = QAction(text, self)
        action.triggered.connect(slot)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        return action

    def _setup_menu(self):
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction(self._make_action("Add Strategy Variant", self._add_strategy, "Ctrl+N"))
        file_menu.addSeparator()
        file_menu.addAction(self._make_action("Pull All Today", self._pull_all_today, "Ctrl+R"))
        file_menu.addAction(self._make_action("Rebuild All Composites", self._rebuild_all_composites))
        file_menu.addSeparator()
        file_menu.addAction(self._make_action("Exit", self.close, "Ctrl+Q"))

        # Data menu
        data_menu = menu_bar.addMenu("Data")
        data_menu.addAction(self._make_action("Refresh Tree", self.strategy_tree.refresh, "F5"))
        data_menu.addAction(self._make_action("Auto-detect NT8 Strategies", self._auto_detect_strategies))
        data_menu.addAction(self._make_action("Import Workspace File...", self._import_workspace_file))
        data_menu.addSeparator()
        data_menu.addAction(self._make_action("Inspect NT8 Database Tables", self._inspect_db))

        # Tools menu
        tools_menu = menu_bar.addMenu("Tools")
        tools_menu.addAction(self._make_action("Settings", self._open_settings, "Ctrl+,"))
        tools_menu.addSeparator()
        tools_menu.addAction(self._make_action("Open Output Folder", self._open_output_folder))

        # Help menu
        help_menu = menu_bar.addMenu("Help")
        help_menu.addAction(self._make_action("About", self._show_about))

    def _setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_nt8 = QLabel("NT8: Checking...")
        self.status_nt8.setObjectName("statusNT8")
        self.status_bar.addPermanentWidget(self.status_nt8)

        self.status_date = QLabel(f"Date: {date.today()}")
        self.status_bar.addPermanentWidget(self.status_date)

        self.status_msg = QLabel("Ready")
        self.status_bar.addWidget(self.status_msg)

        # Update connection status
        if self.reader.is_connected():
            self._on_connection_changed(True)
        else:
            self._on_connection_changed(False)

    # ── Slots ────────────────────────────────────────────────────────────────

    @pyqtSlot()
    def _on_nt8_data_changed(self):
        """NT8 database was updated - refresh live data if viewing today."""
        self.status_msg.setText(f"NT8 data updated at {date.today()}")
        # Refresh live executions display
        exec_df = self.reader.get_executions_today()
        self.data_panel.refresh_live(exec_df)

    @pyqtSlot(bool)
    def _on_connection_changed(self, connected: bool):
        if connected:
            self.status_nt8.setText("● NT8: Connected")
            self.status_nt8.setStyleSheet("color: #69F0AE; font-weight: bold;")
        else:
            self.status_nt8.setText("○ NT8: Not Found")
            self.status_nt8.setStyleSheet("color: #FF6E6E; font-weight: bold;")

    @pyqtSlot(object)
    def _on_strategy_selected(self, params: StrategyParams):
        self.data_panel.show_strategy(params)
        self.claude_terminal.set_active_strategy(params)

    @pyqtSlot(object, object)
    def _on_day_selected(self, params: StrategyParams, target_date: date):
        self.data_panel.show_day(params, target_date)

    @pyqtSlot(object)
    def _on_composite_selected(self, params: StrategyParams):
        self.data_panel.show_composite(params)

    @pyqtSlot(object)
    def _on_analysis_requested(self, params: StrategyParams):
        self.claude_terminal.inject_analysis_request(params)

    # ── Actions ──────────────────────────────────────────────────────────────

    def _add_strategy(self):
        dialog = AddStrategyDialog(parent=self)
        if dialog.exec():
            params = dialog.get_params()
            fp = self.registry.register(params)
            self.organizer.ensure_strategy_dir(params)
            self.strategy_tree.refresh()
            self.status_msg.setText(
                f"Strategy registered: {params.label} | {params.account} | {fp}"
            )

    def _remove_strategy(self, params: StrategyParams):
        reply = QMessageBox.question(
            self,
            "Remove Strategy",
            f"Remove '{params.label} | {params.account}' ({params.fingerprint()}) from the registry?\n\n"
            "This will NOT delete any files. You can re-add the strategy at any time.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.registry.unregister(params.fingerprint())
            self.strategy_tree.refresh()

    def _pull_all_today(self):
        """Pull today's data from NT8 for all registered strategies."""
        strategies = self.registry.all_strategies()
        if not strategies:
            QMessageBox.information(self, "No Strategies", "No strategies registered yet.")
            return

        exec_df = self.reader.get_executions_today()
        if exec_df.empty:
            QMessageBox.warning(
                self,
                "No Data",
                "No execution data found in NT8 database for today.\n\n"
                "Make sure NinjaTrader 8 is running and the database path is correct."
            )
            return

        count = 0
        for params in strategies:
            # Filter executions for this strategy
            if "StrategyName" in exec_df.columns:
                mask = exec_df["StrategyName"].str.contains(params.label, case=False, na=False)
                if "AccountName" in exec_df.columns:
                    mask &= exec_df["AccountName"].str.contains(params.account, case=False, na=False)
                filtered = exec_df[mask]
            else:
                filtered = exec_df

            if not filtered.empty:
                perf_df = self.reader.calculate_performance(filtered)
                self.organizer.save_day_file(params, date.today(), perf_df, filtered)
                count += 1

        self.strategy_tree.refresh()
        self.status_msg.setText(f"Pulled and saved data for {count} strategy variants")
        QMessageBox.information(
            self,
            "Done",
            f"Successfully pulled and saved today's data for {count} strategy variants.\n"
            f"Files saved to: {self._get_output_dir()}"
        )

    def _rebuild_all_composites(self):
        for params in self.registry.all_strategies():
            self.organizer.rebuild_composite(params)
        self.strategy_tree.refresh()
        self.status_msg.setText("All composites rebuilt")

    def _auto_detect_strategies(self):
        """Attempt to read strategy configs from NT8 workspace XMLs."""
        configs = self.reader.get_workspace_strategy_configs()
        if not configs:
            QMessageBox.information(
                self,
                "Auto-detect",
                "No strategy configurations found in NT8 workspace files.\n\n"
                "This may happen if:\n"
                "- NT8 is not installed at the default location\n"
                "- Workspaces path is not set in Settings\n"
                "- NT8 uses a non-standard XML format\n\n"
                "Please add strategies manually using the + button."
            )
            return

        added = 0
        for cfg in configs:
            if not cfg.get("label") or not cfg.get("account"):
                continue
            params = StrategyParams(
                label=cfg["label"],
                account=cfg["account"],
                adx_period=cfg.get("adx_period"),
                protective_stop_ticks=cfg.get("protective_stop_ticks"),
                long_failed_exit=cfg.get("long_failed_exit"),
                short_failed_exit=cfg.get("short_failed_exit"),
                overbought=cfg.get("overbought"),
                oversold=cfg.get("oversold"),
                long_exit_at=cfg.get("long_exit_at"),
                short_exit_at=cfg.get("short_exit_at"),
            )
            self.registry.register(params)
            added += 1

        self.strategy_tree.refresh()
        QMessageBox.information(
            self,
            "Auto-detect Complete",
            f"Detected and registered {added} strategy configurations from workspace files."
        )

    def _import_workspace_file(self):
        """Let the user pick a single NT8 workspace XML and import its strategies."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import NT8 Workspace File",
            str(Path.home()),
            "NT8 Workspace Files (*.xml *.NT8BK *.nt8bk);;All Files (*)",
        )
        if not path:
            return

        configs = self.reader.parse_workspace_file(Path(path))
        if not configs:
            QMessageBox.warning(
                self,
                "Import Workspace",
                f"No strategy configurations found in:\n{path}\n\n"
                "The file may use an unsupported format, or contain no active strategies.",
            )
            return

        added = 0
        for cfg in configs:
            if not cfg.get("label") or not cfg.get("account"):
                continue
            params = StrategyParams(
                label=cfg["label"],
                account=cfg["account"],
                adx_period=cfg.get("adx_period"),
                protective_stop_ticks=cfg.get("protective_stop_ticks"),
                long_failed_exit=cfg.get("long_failed_exit"),
                short_failed_exit=cfg.get("short_failed_exit"),
                overbought=cfg.get("overbought"),
                oversold=cfg.get("oversold"),
                long_exit_at=cfg.get("long_exit_at"),
                short_exit_at=cfg.get("short_exit_at"),
            )
            self.registry.register(params)
            added += 1

        self.strategy_tree.refresh()
        QMessageBox.information(
            self,
            "Import Complete",
            f"Imported {added} strategy configuration(s) from:\n{Path(path).name}",
        )

    def _inspect_db(self):
        tables = self.reader.get_table_names()
        if tables:
            msg = "NT8 Database Tables:\n\n" + "\n".join(f"  • {t}" for t in tables)
        else:
            msg = "Could not connect to NT8 database.\nCheck the path in Settings."
        QMessageBox.information(self, "Database Inspector", msg)

    def _open_settings(self):
        dialog = SettingsDialog(self.config, parent=self)
        if dialog.exec():
            self.config = dialog.get_config()
            self._save_config()

            # Apply new settings
            db_path = self.config.get("nt8_db_path", "")
            if db_path:
                self.reader.set_db_path(db_path)
                self.watcher.db_path = Path(db_path)

            api_key = self.config.get("api_key", "")
            if api_key:
                self.agent.set_api_key(api_key)

            model = self.config.get("model", "claude-sonnet-4-5")
            self.agent.model = model

            output_dir = self._get_output_dir()
            self.organizer = FileOrganizer(output_dir)

            interval = self.config.get("refresh_interval", 5)
            self.watcher.set_interval(interval * 1000)

            self.status_msg.setText("Settings saved")

    def _open_output_folder(self):
        output = str(self._get_output_dir())
        if os.name == "nt":
            os.startfile(output)
        else:
            import subprocess
            subprocess.Popen(["xdg-open", output])

    def _show_about(self):
        QMessageBox.about(
            self,
            "About TraderOS Terminal",
            "<h2>TraderOS Terminal</h2>"
            "<p>NinjaTrader 8 Strategy Performance Monitor</p>"
            "<p>Powered by Claude AI (Anthropic)</p>"
            "<hr>"
            "<p><b>Architecture:</b></p>"
            "<ul>"
            "<li>Real-time execution data from NT8 trade.sqlite</li>"
            "<li>Strategy variant identification by parameter fingerprint</li>"
            "<li>Automatic file organization by label > account > params</li>"
            "<li>Composite performance tracking across all days</li>"
            "<li>Claude AI analysis via Anthropic API</li>"
            "<li>Embedded Chromium research browser</li>"
            "</ul>"
        )

    def _refresh_all(self):
        self.strategy_tree.refresh()

    # ── Window State ─────────────────────────────────────────────────────────

    def _restore_geometry(self):
        settings = QSettings("TraderOS", "Terminal")
        geo = settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        state = settings.value("windowState")
        if state:
            self.restoreState(state)

    def closeEvent(self, event):
        settings = QSettings("TraderOS", "Terminal")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        self.watcher.stop()
        super().closeEvent(event)
