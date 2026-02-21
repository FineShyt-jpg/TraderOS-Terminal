#!/usr/bin/env python3
"""
TraderOS Terminal - Entry Point

NinjaTrader 8 Strategy Performance Monitor
Powered by Claude AI (Anthropic)
"""

import sys
import os
from pathlib import Path


def check_dependencies():
    """Check for required packages before launching."""
    missing = []
    try:
        import PyQt6
    except ImportError:
        missing.append("PyQt6")
    try:
        import anthropic
    except ImportError:
        missing.append("anthropic")
    try:
        import pandas
    except ImportError:
        missing.append("pandas")

    if missing:
        print("=" * 60)
        print("TraderOS Terminal - Missing Dependencies")
        print("=" * 60)
        print(f"\nMissing packages: {', '.join(missing)}")
        print("\nInstall with:")
        print("  pip install " + " ".join(missing))
        print("\nOr run the install script:")
        print("  Windows: install.bat")
        print("  Linux/Mac: bash install.sh")
        sys.exit(1)


def main():
    check_dependencies()

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt, QCoreApplication
    from PyQt6.QtGui import QFont

    # WebEngine MUST be imported before QApplication is created.
    # When running as root (CI/containers), Chrome requires --no-sandbox.
    if hasattr(os, "getuid") and os.getuid() == 0:
        os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")
    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    except ImportError:
        pass

    # Enable high DPI (attribute removed in Qt 6.7+, guard for compatibility)
    try:
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    except AttributeError:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("TraderOS Terminal")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("TraderOS")

    # Default monospace font
    font = QFont("Consolas", 10)
    if not font.exactMatch():
        font = QFont("Courier New", 10)
    app.setFont(font)

    # Load stylesheet
    style_path = Path(__file__).parent / "assets" / "style.qss"
    if style_path.exists():
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    else:
        print(f"Warning: stylesheet not found at {style_path}")

    # Set ANTHROPIC_API_KEY from environment if not already set
    # (will be overridden by config if user set it in Settings)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    # Set API key in agent if provided via environment
    if api_key and not window.config.get("api_key"):
        window.agent.set_api_key(api_key)
        window.config["api_key"] = api_key

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
