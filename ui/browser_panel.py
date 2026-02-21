"""
Research Browser Panel

Full Chromium browser embedded via PyQt6-WebEngine.
Includes a Claude-powered research assistant that can analyze
web content in context of your strategy data.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QToolButton, QLabel, QProgressBar, QSplitter, QTextEdit,
    QTabWidget
)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineProfile
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False


class BrowserPanel(QWidget):
    """
    Embedded Chromium browser with address bar, navigation, and
    Claude research assistant integration.
    """

    page_title_changed = pyqtSignal(str)

    DEFAULT_URLS = [
        ("TradingView", "https://www.tradingview.com"),
        ("CME Group", "https://www.cmegroup.com"),
        ("Futures.io", "https://futures.io"),
        ("Finviz", "https://finviz.com"),
        ("Barchart", "https://www.barchart.com"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Browser header
        header = QWidget()
        header.setObjectName("browserHeader")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(6, 4, 6, 4)
        h_layout.setSpacing(4)

        icon = QLabel("🌐")
        h_layout.addWidget(icon)

        title = QLabel("RESEARCH TERMINAL")
        title.setObjectName("browserTitle")
        h_layout.addWidget(title)
        h_layout.addStretch()
        layout.addWidget(header)

        if not WEBENGINE_AVAILABLE:
            self._setup_fallback(layout)
            return

        # Navigation bar
        nav_bar = QWidget()
        nav_bar.setObjectName("navBar")
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(6, 4, 6, 4)
        nav_layout.setSpacing(4)

        self.btn_back = QToolButton()
        self.btn_back.setText("◀")
        self.btn_back.setObjectName("navButton")
        nav_layout.addWidget(self.btn_back)

        self.btn_forward = QToolButton()
        self.btn_forward.setText("▶")
        self.btn_forward.setObjectName("navButton")
        nav_layout.addWidget(self.btn_forward)

        self.btn_reload = QToolButton()
        self.btn_reload.setText("↻")
        self.btn_reload.setObjectName("navButton")
        nav_layout.addWidget(self.btn_reload)

        self.btn_home = QToolButton()
        self.btn_home.setText("⌂")
        self.btn_home.setObjectName("navButton")
        self.btn_home.clicked.connect(lambda: self.navigate("https://www.tradingview.com"))
        nav_layout.addWidget(self.btn_home)

        self.address_bar = QLineEdit()
        self.address_bar.setObjectName("addressBar")
        self.address_bar.setPlaceholderText("Enter URL or search...")
        self.address_bar.returnPressed.connect(self._navigate_from_bar)
        nav_layout.addWidget(self.address_bar)

        self.btn_go = QPushButton("Go")
        self.btn_go.setObjectName("goButton")
        self.btn_go.clicked.connect(self._navigate_from_bar)
        nav_layout.addWidget(self.btn_go)

        layout.addWidget(nav_bar)

        # Quick links bar
        links_bar = QWidget()
        links_bar.setObjectName("linksBar")
        lb_layout = QHBoxLayout(links_bar)
        lb_layout.setContentsMargins(6, 2, 6, 2)
        lb_layout.setSpacing(4)

        for name, url in self.DEFAULT_URLS:
            btn = QPushButton(name)
            btn.setObjectName("quickLinkBtn")
            btn.clicked.connect(lambda checked, u=url: self.navigate(u))
            lb_layout.addWidget(btn)
        lb_layout.addStretch()
        layout.addWidget(links_bar)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("browserProgress")
        self.progress_bar.setMaximumHeight(3)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Web view
        self.web_view = QWebEngineView()
        self.web_view.setObjectName("webView")

        # Connect navigation buttons
        self.btn_back.clicked.connect(self.web_view.back)
        self.btn_forward.clicked.connect(self.web_view.forward)
        self.btn_reload.clicked.connect(self.web_view.reload)

        # Connect web view signals
        self.web_view.urlChanged.connect(self._on_url_changed)
        self.web_view.loadProgress.connect(self._on_load_progress)
        self.web_view.loadFinished.connect(self._on_load_finished)
        self.web_view.titleChanged.connect(self.page_title_changed.emit)

        layout.addWidget(self.web_view)

        # Load default page
        self.navigate("https://www.tradingview.com")

    def _setup_fallback(self, layout):
        """Fallback UI when WebEngine is not installed."""
        fallback = QTextEdit()
        fallback.setReadOnly(True)
        fallback.setObjectName("fallbackBrowser")
        fallback.setHtml("""
        <div style="padding: 24px; font-family: monospace; color: #888;">
            <h2 style="color: #64B5F6;">Browser Not Available</h2>
            <p>PyQt6-WebEngine is not installed.</p>
            <p>Install it with:</p>
            <pre style="background: #1a1a2e; padding: 12px; border-radius: 4px;">
pip install PyQt6-WebEngine</pre>
            <p>Then restart the application.</p>
        </div>
        """)
        layout.addWidget(fallback)

    def navigate(self, url: str):
        if not WEBENGINE_AVAILABLE:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self.web_view.setUrl(QUrl(url))

    def _navigate_from_bar(self):
        text = self.address_bar.text().strip()
        if not text:
            return
        if "." in text and " " not in text:
            self.navigate(text)
        else:
            # Treat as search query
            query = text.replace(" ", "+")
            self.navigate(f"https://www.google.com/search?q={query}")

    def _on_url_changed(self, url: QUrl):
        self.address_bar.setText(url.toString())

    def _on_load_progress(self, progress: int):
        if progress < 100:
            self.progress_bar.show()
            self.progress_bar.setValue(progress)
        else:
            self.progress_bar.hide()

    def _on_load_finished(self, ok: bool):
        self.progress_bar.hide()
