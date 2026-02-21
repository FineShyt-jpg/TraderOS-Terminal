#!/usr/bin/env bash
# TraderOS Terminal - Linux/Mac Installer

set -e

echo "============================================================"
echo "TraderOS Terminal - Installing Dependencies"
echo "============================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is not installed."
    echo "Install with: sudo apt install python3 python3-pip (Debian/Ubuntu)"
    exit 1
fi

python3 --version
echo ""

# Upgrade pip
echo "Upgrading pip..."
python3 -m pip install --upgrade pip

echo ""
echo "Installing dependencies..."
python3 -m pip install \
    "PyQt6>=6.6.0" \
    "PyQt6-WebEngine>=6.6.0" \
    "anthropic>=0.34.0" \
    "pandas>=2.1.0" \
    "watchdog>=4.0.0" \
    "python-dateutil>=2.9.0" \
    "numpy>=1.26.0"

echo ""
echo "============================================================"
echo "Installation complete!"
echo "============================================================"
echo ""
echo "To run TraderOS Terminal:"
echo "  python3 main.py"
echo ""
echo "To set your Anthropic API key:"
echo "  export ANTHROPIC_API_KEY=sk-ant-..."
echo "  python3 main.py"
echo ""
