"""Runtime dependency checks for the AI Language Explainer add-on."""

from __future__ import annotations

import os
import subprocess
import sys
from aqt.utils import tooltip


def check_dependencies() -> None:
    """Install required dependencies when they are missing."""

    try:
        import requests  # noqa: F401
    except ImportError:
        tooltip("Installing required dependencies for AI Language Explainer addon...")

        addon_dir = os.path.dirname(os.path.abspath(__file__))
        addon_root = os.path.dirname(addon_dir)
        requirements_path = os.path.join(addon_root, "requirements.txt")

        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_path])
        tooltip("Dependencies installed successfully!")


__all__ = ["check_dependencies"]
