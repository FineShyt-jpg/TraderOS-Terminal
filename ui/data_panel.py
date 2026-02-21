"""
Data Panel

Right-side content area showing:
 - Strategy overview (params + summary stats)
 - Day performance table
 - Composite table
 - Live trade feed
"""

from datetime import date
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QScrollArea, QFrame, QSplitter, QPushButton, QGroupBox,
    QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush
import pandas as pd

from core.strategy_fingerprint import StrategyParams
from core.file_organizer import FileOrganizer
from core.nt8_reader import NT8Reader


class MetricCard(QFrame):
    """A small card displaying a single metric value."""

    def __init__(self, label: str, value: str = "--", parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("metricValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.name_label = QLabel(label)
        self.name_label.setObjectName("metricName")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.value_label)
        layout.addWidget(self.name_label)

    def set_value(self, value: str, positive: bool = None):
        self.value_label.setText(value)
        if positive is True:
            self.value_label.setStyleSheet("color: #69F0AE;")
        elif positive is False:
            self.value_label.setStyleSheet("color: #FF6E6E;")
        else:
            self.value_label.setStyleSheet("")


class PerformanceSummaryWidget(QWidget):
    """Shows metric cards for a strategy's performance."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self.cards = {}
        metrics = [
            ("NetPnL", "Net P&L"),
            ("TotalTrades", "Trades"),
            ("WinRate", "Win Rate"),
            ("ProfitFactor", "Prof. Factor"),
            ("AvgWin", "Avg Win"),
            ("AvgLoss", "Avg Loss"),
            ("GrossProfit", "Gross Profit"),
            ("Commission", "Commission"),
        ]

        for idx, (key, label) in enumerate(metrics):
            card = MetricCard(label)
            self.cards[key] = card
            row, col = divmod(idx, 4)
            layout.addWidget(card, row, col)

    def update_from_df(self, df: pd.DataFrame):
        """Populate cards from a performance DataFrame row (or aggregate)."""
        if df.empty:
            for card in self.cards.values():
                card.set_value("--")
            return

        # Aggregate if multiple instruments
        numeric_cols = df.select_dtypes(include="number").columns
        agg = df[numeric_cols].sum()
        if "WinRate" in df.columns:
            agg["WinRate"] = df["WinRate"].mean()
        if "ProfitFactor" in df.columns:
            gross_p = df["GrossProfit"].sum() if "GrossProfit" in df else 0
            gross_l = abs(df["GrossLoss"].sum()) if "GrossLoss" in df else 0
            agg["ProfitFactor"] = gross_p / gross_l if gross_l > 0 else 999.0

        for key, card in self.cards.items():
            val = agg.get(key, None)
            if val is None:
                card.set_value("--")
                continue
            if key == "NetPnL":
                card.set_value(f"${val:,.2f}", positive=val >= 0)
            elif key == "WinRate":
                card.set_value(f"{val:.1f}%", positive=val >= 50)
            elif key == "ProfitFactor":
                card.set_value(f"{val:.2f}", positive=val >= 1.0)
            elif key in ("AvgWin", "AvgLoss", "GrossProfit", "Commission", "GrossLoss"):
                pv = None
                if key == "AvgWin":
                    pv = True
                elif key in ("AvgLoss", "GrossLoss", "Commission"):
                    pv = False
                card.set_value(f"${val:,.2f}", positive=pv)
            elif key == "TotalTrades":
                card.set_value(str(int(val)))
            else:
                card.set_value(str(round(val, 2)))


class DataTable(QTableWidget):
    """Generic styled table for performance data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dataTable")
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)

    def load_dataframe(self, df: pd.DataFrame):
        self.clear()
        if df.empty:
            self.setRowCount(0)
            self.setColumnCount(0)
            return

        self.setRowCount(len(df))
        self.setColumnCount(len(df.columns))
        self.setHorizontalHeaderLabels(list(df.columns))

        for row_idx, row in df.iterrows():
            for col_idx, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # Color P&L values
                col_name = df.columns[col_idx]
                if col_name in ("NetPnL", "GrossPnL") and isinstance(val, (int, float)):
                    if float(val) > 0:
                        item.setForeground(QBrush(QColor("#69F0AE")))
                    elif float(val) < 0:
                        item.setForeground(QBrush(QColor("#FF6E6E")))

                self.setItem(row_idx, col_idx, item)

        self.resizeColumnsToContents()


class DataPanel(QWidget):
    """
    Main content panel - shows strategy data in tabs.
    Tabs: Overview | Today | Composite | Live Feed | Description
    """

    analysis_requested = pyqtSignal(object)   # StrategyParams

    def __init__(self, organizer: FileOrganizer, reader: NT8Reader, parent=None):
        super().__init__(parent)
        self.organizer = organizer
        self.reader = reader
        self._current_params: StrategyParams = None
        self._current_date: date = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self.header_label = QLabel("Select a strategy from the tree")
        self.header_label.setObjectName("panelHeader")
        self.header_label.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(self.header_label)

        # Metric cards row
        self.perf_summary = PerformanceSummaryWidget()
        layout.addWidget(self.perf_summary)

        # Action buttons
        btn_bar = QWidget()
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(12, 4, 12, 4)

        self.btn_pull = QPushButton("⬇  Pull Today's Data")
        self.btn_pull.setObjectName("actionButton")
        self.btn_pull.clicked.connect(self._pull_today)
        btn_layout.addWidget(self.btn_pull)

        self.btn_analyze = QPushButton("🧠  AI Analysis")
        self.btn_analyze.setObjectName("actionButton")
        self.btn_analyze.clicked.connect(self._request_analysis)
        btn_layout.addWidget(self.btn_analyze)

        self.btn_rebuild = QPushButton("↻  Rebuild Composite")
        self.btn_rebuild.setObjectName("secondaryButton")
        self.btn_rebuild.clicked.connect(self._rebuild_composite)
        btn_layout.addWidget(self.btn_rebuild)
        btn_layout.addStretch()

        layout.addWidget(btn_bar)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setObjectName("dataTabs")
        layout.addWidget(self.tabs)

        # Tab: Overview
        self.tab_overview = QTextEdit()
        self.tab_overview.setReadOnly(True)
        self.tab_overview.setObjectName("overviewText")
        self.tabs.addTab(self.tab_overview, "Overview")

        # Tab: Today
        today_widget = QWidget()
        today_layout = QVBoxLayout(today_widget)
        today_layout.setContentsMargins(4, 4, 4, 4)
        self.table_today = DataTable()
        today_layout.addWidget(self.table_today)
        self.tabs.addTab(today_widget, "Today")

        # Tab: Composite
        comp_widget = QWidget()
        comp_layout = QVBoxLayout(comp_widget)
        comp_layout.setContentsMargins(4, 4, 4, 4)
        self.table_composite = DataTable()
        comp_layout.addWidget(self.table_composite)
        self.tabs.addTab(comp_widget, "Composite")

        # Tab: Live Executions
        live_widget = QWidget()
        live_layout = QVBoxLayout(live_widget)
        live_layout.setContentsMargins(4, 4, 4, 4)
        self.table_live = DataTable()
        live_layout.addWidget(self.table_live)
        self.tabs.addTab(live_widget, "Live Executions")

        # Tab: Parameters
        self.tab_params = QTextEdit()
        self.tab_params.setReadOnly(True)
        self.tab_params.setObjectName("overviewText")
        self.tabs.addTab(self.tab_params, "Parameters")

    def show_strategy(self, params: StrategyParams):
        """Display overview + composite for a strategy variant."""
        self._current_params = params
        self._current_date = None
        self.header_label.setText(
            f"{params.label}  ▸  {params.account}  ▸  {params.short_description()}"
        )

        self.tab_params.setPlainText(params.full_description())

        # Load composite
        composite = self.organizer.get_composite(params)
        self.table_composite.load_dataframe(composite)

        # Load today
        today_df = self.organizer.get_day_file(params, date.today())
        self.table_today.load_dataframe(today_df)
        if not today_df.empty:
            self.perf_summary.update_from_df(today_df)
        elif not composite.empty:
            self.perf_summary.update_from_df(composite)
        else:
            self.perf_summary.update_from_df(pd.DataFrame())

        self._build_overview(params, today_df, composite)
        self.tabs.setCurrentIndex(0)

    def show_day(self, params: StrategyParams, target_date: date):
        """Display a specific day's data."""
        self._current_params = params
        self._current_date = target_date
        self.header_label.setText(
            f"{params.label}  ▸  {params.account}  ▸  {target_date.strftime('%Y-%m-%d')}"
        )
        df = self.organizer.get_day_file(params, target_date)
        self.table_today.load_dataframe(df)
        self.perf_summary.update_from_df(df)
        self.tabs.setCurrentIndex(1)

    def show_composite(self, params: StrategyParams):
        """Display the composite file."""
        self._current_params = params
        self.header_label.setText(
            f"{params.label}  ▸  {params.account}  ▸  Composite (All Days)"
        )
        df = self.organizer.get_composite(params)
        self.table_composite.load_dataframe(df)
        if not df.empty:
            self.perf_summary.update_from_df(df)
        self.tabs.setCurrentIndex(2)

    def refresh_live(self, executions_df: pd.DataFrame, params: StrategyParams = None):
        """Update the live executions tab with fresh NT8 data."""
        if params:
            # Filter for this strategy
            if "StrategyName" in executions_df.columns:
                mask = executions_df["StrategyName"].str.contains(
                    params.label, case=False, na=False
                )
                if "AccountName" in executions_df.columns:
                    mask &= executions_df["AccountName"].str.contains(
                        params.account, case=False, na=False
                    )
                executions_df = executions_df[mask]

        self.table_live.load_dataframe(executions_df)

    def _build_overview(self, params: StrategyParams, today: pd.DataFrame, composite: pd.DataFrame):
        lines = []
        lines.append(f"STRATEGY: {params.label}")
        lines.append(f"ACCOUNT:  {params.account}")
        lines.append(f"VARIANT:  {params.fingerprint()}")
        lines.append("")
        lines.append(params.full_description())
        lines.append("")

        if not today.empty:
            lines.append(f"── TODAY ({date.today()}) ──────────────────────")
            if "NetPnL" in today.columns:
                total = today["NetPnL"].sum()
                lines.append(f"  Net P&L:     ${total:,.2f}")
            if "TotalTrades" in today.columns:
                lines.append(f"  Trades:      {int(today['TotalTrades'].sum())}")
            if "WinRate" in today.columns:
                lines.append(f"  Win Rate:    {today['WinRate'].mean():.1f}%")
            lines.append("")

        if not composite.empty:
            lines.append(f"── COMPOSITE ({len(composite)} days) ──────────────────")
            if "NetPnL" in composite.columns:
                total = composite["NetPnL"].sum()
                avg = composite["NetPnL"].mean()
                best = composite["NetPnL"].max()
                worst = composite["NetPnL"].min()
                lines.append(f"  Total Net P&L: ${total:,.2f}")
                lines.append(f"  Avg Daily:     ${avg:,.2f}")
                lines.append(f"  Best Day:      ${best:,.2f}")
                lines.append(f"  Worst Day:     ${worst:,.2f}")
            if "WinRate" in composite.columns:
                lines.append(f"  Avg Win Rate:  {composite['WinRate'].mean():.1f}%")
            if "TotalTrades" in composite.columns:
                lines.append(f"  Total Trades:  {int(composite['TotalTrades'].sum())}")

        self.tab_overview.setPlainText("\n".join(lines))

    def _pull_today(self):
        """Pull today's live data from NT8 for the current strategy."""
        if not self._current_params:
            return
        params = self._current_params
        today = date.today()

        # Pull executions from NT8
        exec_df = self.reader.get_executions_today()
        if exec_df.empty:
            self.tab_overview.setPlainText(
                "No executions found in NT8 database for today.\n\n"
                "Make sure NinjaTrader 8 is running and the database path is correct.\n"
                "Check Tools > Settings > NT8 Database Path."
            )
            return

        # Filter for this strategy
        if "StrategyName" in exec_df.columns:
            mask = exec_df["StrategyName"].str.contains(params.label, case=False, na=False)
            if "AccountName" in exec_df.columns:
                mask &= exec_df["AccountName"].str.contains(params.account, case=False, na=False)
            filtered = exec_df[mask]
        else:
            filtered = exec_df

        # Calculate performance
        perf_df = self.reader.calculate_performance(filtered)

        # Save to files
        day_path = self.organizer.save_day_file(params, today, perf_df, filtered)

        # Refresh display
        self.show_strategy(params)
        self.tabs.setCurrentIndex(1)  # Jump to Today tab

        # Update live tab
        self.table_live.load_dataframe(filtered)

    def _request_analysis(self):
        if self._current_params:
            self.analysis_requested.emit(self._current_params)

    def _rebuild_composite(self):
        if self._current_params:
            self.organizer.rebuild_composite(self._current_params)
            self.show_strategy(self._current_params)
