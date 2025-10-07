"""Entry point for the AI Language Explainer add-on."""

from __future__ import annotations

import traceback

from aqt import gui_hooks

from .alx.config import (
    CONFIG,
    get_fields_for_note_type,
    get_note_types,
    load_config,
    save_config,
    set_addon_module_name,
)
from .alx.dependencies import check_dependencies
from .alx.logging import debug_log, setup_crash_handler
from .alx.menu import batch_process_notes, open_settings, setup_menu
from .alx.processing import process_note, process_note_debug
from .alx.reviewer import (
    add_button_to_reviewer,
    on_card_shown,
    on_js_message,
    process_current_card,
)
from .alx.ui.bulk_dialog import BulkGenerationDialog
from .alx.ui.config_dialog import ConfigDialog


setup_crash_handler()
check_dependencies()
set_addon_module_name(__name__)


def init() -> None:
    try:
        debug_log("Initializing AI Language Explainer addon")

        load_config()
        debug_log(f"Configuration loaded: {CONFIG}")

        setup_menu()
        debug_log("Menu setup complete")

        debug_log("Registering hooks")
        gui_hooks.reviewer_did_show_answer.append(on_card_shown)
        debug_log("Registered reviewer_did_show_answer hook")
        gui_hooks.webview_did_receive_js_message.append(on_js_message)
        debug_log("Registered webview_did_receive_js_message hook")

        debug_log("AI Language Explainer addon initialization complete")
    except Exception as err:
        debug_log(f"Error during initialization: {err}")
        debug_log(traceback.format_exc())


init()


__all__ = [
    "CONFIG",
    "BulkGenerationDialog",
    "ConfigDialog",
    "add_button_to_reviewer",
    "batch_process_notes",
    "debug_log",
    "get_fields_for_note_type",
    "get_note_types",
    "load_config",
    "open_settings",
    "process_current_card",
    "process_note",
    "process_note_debug",
    "save_config",
    "setup_menu",
]
