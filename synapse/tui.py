from __future__ import annotations

import subprocess
from pathlib import Path


def run_tui(color: bool = True, unicode_logo: bool = False) -> None:
    """Launch the optional Ink terminal frontend when Node dependencies exist."""
    root = Path(__file__).resolve().parents[1]
    terminal_ui = root / "terminal-ui"
    package_json = terminal_ui / "package.json"
    node_modules = terminal_ui / "node_modules"

    if not package_json.exists():
        print("Synapse terminal UI is not installed in this package.")
        return

    if not node_modules.exists():
        print("Synapse terminal UI dependencies are not installed.")
        print()
        print("Install them with:")
        print("  cd terminal-ui")
        print("  npm install")
        print()
        print("Then start the Python API in another terminal:")
        print("  python synapse.py --api")
        print()
        print("And run:")
        print("  npm start")
        return

    command = ["npm", "start"]
    if not color:
        command.extend(["--", "--no-color"])
    if unicode_logo:
        command.extend(["--", "--unicode"])
    try:
        subprocess.run(command, cwd=terminal_ui, check=False)
    except FileNotFoundError:
        print("npm was not found. Install Node.js, then run the terminal UI from terminal-ui/.")
