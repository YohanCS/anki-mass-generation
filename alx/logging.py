"""Logging and crash handling utilities for the AI Language Explainer add-on."""

from __future__ import annotations

import atexit
import os
import platform
import sys
import time
from typing import Any

from aqt import mw


def debug_log(message: Any) -> None:
    """Write debug messages to a dedicated log file."""
    try:
        addon_dir = os.path.dirname(os.path.abspath(__file__))
        # Resolve to the add-on root (one level up from this module)
        addon_root = os.path.dirname(addon_dir)
        debug_log_path = os.path.join(addon_root, "debug_log.txt")

        with open(debug_log_path, "a", encoding="utf-8") as handle:
            handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception as err:  # pragma: no cover - never raise during logging
        print(f"Failed to write to debug log: {err}")


def setup_crash_handler() -> None:
    """Log environment information when Anki shuts down."""

    addon_dir = os.path.dirname(os.path.abspath(__file__))
    addon_root = os.path.dirname(addon_dir)
    crash_log_path = os.path.join(addon_root, "crash_log.txt")

    def log_system_info() -> None:
        try:
            with open(crash_log_path, "a", encoding="utf-8") as handle:
                handle.write(
                    f"\n\n=== SYSTEM INFO [{time.strftime('%Y-%m-%d %H:%M:%S')}] ===\n"
                )
                handle.write(f"Platform: {platform.platform()}\n")
                handle.write(f"Python: {sys.version}\n")
                handle.write(f"Anki version: {mw.pm.meta.get('version', 'unknown')}\n")

                try:
                    from aqt.qt import QT_VERSION_STR

                    handle.write(f"Qt version: {QT_VERSION_STR}\n")
                except Exception:
                    handle.write("Qt version: unknown\n")

                handle.write("=== END SYSTEM INFO ===\n\n")
        except Exception as err:
            print(f"Failed to log system info: {err}")

    atexit.register(log_system_info)
    log_system_info()


__all__ = ["debug_log", "setup_crash_handler"]
