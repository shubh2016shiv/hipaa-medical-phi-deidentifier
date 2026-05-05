#!/usr/bin/env python3
"""
SecurePHI — UI Launcher

Starts the Flask-based HTML/CSS/JS interface.
The old Dash UI (dash_ui.py / start_dash_ui.py) is superseded by this.

Usage:
    python start_ui.py
    # → http://localhost:8050
"""

import subprocess
import sys


def main() -> None:
    print("=" * 60)
    print("  SecurePHI — HIPAA De-identification Interface")
    print("  Open your browser at:  http://localhost:8050")
    print("  Press Ctrl+C to stop.")
    print("=" * 60)
    try:
        subprocess.run([sys.executable, "server.py"], check=True)
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
