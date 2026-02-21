"""
Strategy Tree Panel

Hierarchical tree showing:
  Label
  └── Account
      └── Param Variant (short description)
          ├── 2026-02-21 (today - active)
          ├── 2026-02-20
          └── composite
"""

from pathlib import Path
from datetime import date
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QMenu, QMessageBox, QToolButton, QLineEdit,
    QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QColor, QBrush, QCursor

from core.strategy_fingerprint import StrategyRegistry, StrategyParams
from core.file_organizer import FileOrganizer


class StrategyTreeWidget(QWidget):
    """
    Left panel: hierarchical view of all registered strategy variants
    and their day/composite files.
    """

    # Signals emitted when user selects something
    strategy_selected = pyqtSignal(object)          # StrategyParams
    day_selected = pyqtSignal(object, object)       # StrategyParams, date
    composite_selected = pyqtSignal(object)         # StrategyParams
    add_strategy_requested = pyqtSignal()
    remove_strategy_requested = pyqtSignal(object)  # StrategyParams

    ICON_LABEL    = "📊"
    ICON_ACCOUNT  = "🏦"
    ICON_VARIANT  = "⚙️"
    ICON_DAY      = "📅"
    ICON_TODAY    = "🔴"   # Active / live
    ICON_COMP     = "📈"

    def __init__(self, registry: StrategyRegistry, organizer: FileOrganizer, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.organizer = organizer
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QWidget()
        header.setObjectName("treeHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 6, 8, 6)

        title = QLabel("STRATEGIES")
        title.setObjectName("treePanelTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()

        btn_add = QToolButton()
        btn_add.setText("+")
        btn_add.setToolTip("Add strategy variant")
        btn_add.setObjectName("iconButton")
        btn_add.clicked.connect(self.add_strategy_requested.emit)
        header_layout.addWidget(btn_add)

        btn_refresh = QToolButton()
        btn_refresh.setText("↻")
        btn_refresh.setToolTip("Refresh tree")
        btn_refresh.setObjectName("iconButton")
        btn_refresh.clicked.connect(self.refresh)
        header_layout.addWidget(btn_refresh)

        layout.addWidget(header)

        # Search bar
        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Filter strategies...")
        search_bar.setObjectName("searchBar")
        search_bar.textChanged.connect(self._filter)
        layout.addWidget(search_bar)
        self._search_bar = search_bar

        # Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setObjectName("strategyTree")
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.setIndentation(16)
        self.tree.setAnimated(True)
        layout.addWidget(self.tree)

    def refresh(self):
        """Rebuild the entire tree from the registry and file system."""
        self.tree.clear()
        today = date.today()

        label_map = self.registry.get_label_account_map()
        if not label_map:
            placeholder = QTreeWidgetItem(["  No strategies registered"])
            placeholder.setForeground(0, QBrush(QColor("#888")))
            self.tree.addTopLevelItem(placeholder)
            return

        for label in sorted(label_map.keys()):
            label_item = QTreeWidgetItem([f"{self.ICON_LABEL}  {label}"])
            label_item.setData(0, Qt.ItemDataRole.UserRole, ("label", label))
            font = label_item.font(0)
            font.setBold(True)
            font.setPointSize(10)
            label_item.setFont(0, font)
            label_item.setForeground(0, QBrush(QColor("#64B5F6")))
            self.tree.addTopLevelItem(label_item)

            accounts = sorted(label_map[label])
            for account in accounts:
                acc_item = QTreeWidgetItem([f"  {self.ICON_ACCOUNT}  {account}"])
                acc_item.setData(0, Qt.ItemDataRole.UserRole, ("account", label, account))
                acc_item.setForeground(0, QBrush(QColor("#A5D6A7")))
                label_item.addChild(acc_item)

                variants = self.registry.get_variants_for_label_account(label, account)
                for params in variants:
                    desc = params.short_description()
                    var_item = QTreeWidgetItem([f"    {self.ICON_VARIANT}  {desc}"])
                    var_item.setData(0, Qt.ItemDataRole.UserRole, ("variant", params))
                    var_item.setToolTip(0, params.full_description())
                    var_item.setForeground(0, QBrush(QColor("#E0E0E0")))
                    acc_item.addChild(var_item)

                    # Day files
                    day_files = self.organizer.list_day_files(params)
                    for d in day_files:
                        if d == today:
                            label_text = f"      {self.ICON_TODAY}  {d.strftime('%Y-%m-%d')}  ← LIVE"
                        else:
                            label_text = f"      {self.ICON_DAY}  {d.strftime('%Y-%m-%d')}"
                        day_item = QTreeWidgetItem([label_text])
                        day_item.setData(0, Qt.ItemDataRole.UserRole, ("day", params, d))
                        if d == today:
                            day_item.setForeground(0, QBrush(QColor("#FF6E6E")))
                        else:
                            day_item.setForeground(0, QBrush(QColor("#BDBDBD")))
                        var_item.addChild(day_item)

                    # Composite
                    composite_item = QTreeWidgetItem([f"      {self.ICON_COMP}  composite (all days)"])
                    composite_item.setData(0, Qt.ItemDataRole.UserRole, ("composite", params))
                    composite_item.setForeground(0, QBrush(QColor("#FFD54F")))
                    var_item.addChild(composite_item)

            label_item.setExpanded(True)
            for i in range(label_item.childCount()):
                acc = label_item.child(i)
                acc.setExpanded(True)
                for j in range(acc.childCount()):
                    var = acc.child(j)
                    var.setExpanded(True)

        self._filter(self._search_bar.text())

    def _on_item_clicked(self, item: QTreeWidgetItem, col: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        kind = data[0]
        if kind == "variant":
            self.strategy_selected.emit(data[1])
        elif kind == "day":
            self.day_selected.emit(data[1], data[2])
        elif kind == "composite":
            self.composite_selected.emit(data[1])

    def _context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        menu = QMenu(self)
        menu.setObjectName("contextMenu")

        if data[0] == "variant":
            params: StrategyParams = data[1]
            action_remove = menu.addAction("Remove Strategy Variant")
            action_rebuild = menu.addAction("Rebuild Composite")
            action_desc = menu.addAction("Show Full Description")
            action = menu.exec(QCursor.pos())
            if action == action_remove:
                self.remove_strategy_requested.emit(params)
            elif action == action_rebuild:
                from core.file_organizer import FileOrganizer
                self.organizer.rebuild_composite(params)
                self.refresh()
            elif action == action_desc:
                msg = QMessageBox(self)
                msg.setWindowTitle("Strategy Parameters")
                msg.setText(params.full_description())
                msg.exec()

        elif data[0] in ("day", "composite"):
            menu.addAction("Open in Viewer").setEnabled(False)
            menu.exec(QCursor.pos())

    def _filter(self, text: str):
        text = text.lower()
        for i in range(self.tree.topLevelItemCount()):
            self._filter_item(self.tree.topLevelItem(i), text)

    def _filter_item(self, item: QTreeWidgetItem, text: str) -> bool:
        visible = text in item.text(0).lower()
        child_visible = False
        for i in range(item.childCount()):
            if self._filter_item(item.child(i), text):
                child_visible = True
        show = visible or child_visible
        item.setHidden(not show)
        return show
