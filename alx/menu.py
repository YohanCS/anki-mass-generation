"""Menus and batch processing entry points."""

from __future__ import annotations

import threading
import traceback

from aqt import gui_hooks, mw
from aqt.browser import Browser
from aqt.qt import QAction, QDialog, QMenu, QMessageBox, QProgressDialog, Qt
from aqt.utils import qconnect, showInfo

from .config import CONFIG
from .logging import debug_log
from .processing import process_note
from .ui.bulk_dialog import BulkGenerationDialog
from .ui.config_dialog import ConfigDialog


def setup_menu():
    # Create main menu for AI Language Explainer
    ai_explainer_menu = QMenu("AI Language Explainer", mw)
    
    # Add settings as a submenu option
    settings_action = QAction("Settings", mw)
    qconnect(settings_action.triggered, open_settings)
    ai_explainer_menu.addAction(settings_action)
    
    # Add the menu to the Tools menu
    mw.form.menuTools.addMenu(ai_explainer_menu)
    
    # Enable browser menu action for bulk processing
    debug_log("Registering browser_menus_did_init hook for batch processing")
    gui_hooks.browser_menus_did_init.append(setup_browser_menu)
    debug_log("Browser hook registered")


def open_settings():
    dialog = ConfigDialog(mw)
    dialog.exec()


def batch_process_notes():
    browser = mw.app.activeWindow()
    if not isinstance(browser, Browser):
        showInfo("Please open this from the Browser view")
        return
    
    # Get selected note ids
    selected_notes = browser.selectedNotes()
    if not selected_notes:
        showInfo("No cards selected. Please select cards to process.")
        return
    
    # Check if configuration is loaded
    if not CONFIG["openai_key"]:
        showInfo("Please set your OpenAI API key in the AI Language Explainer Settings.")
        return
    
    # Show the bulk generation options dialog with selected notes for analysis
    bulk_dialog = BulkGenerationDialog(mw, selected_notes)
    if bulk_dialog.exec() != QDialog.DialogCode.Accepted:
        debug_log("User canceled bulk generation dialog")
        return
    
    # Get the generation options from the dialog (4 values: generate_text, generate_audio, override_text, override_audio)
    generate_text, generate_audio, override_text, override_audio = bulk_dialog.get_generation_options()
    debug_log(f"Bulk generation options: generate_text={generate_text}, generate_audio={generate_audio}, override_text={override_text}, override_audio={override_audio}")
    
    # Store generation flags for backend processing
    CONFIG["generate_text"] = generate_text
    CONFIG["generate_audio"] = generate_audio
    CONFIG["override_text"] = override_text
    CONFIG["override_audio"] = override_audio
    
    # Create a progress dialog with fixed width to avoid the resizing issue
    progress = QProgressDialog("Processing cards...", "Cancel", 0, len(selected_notes) + 1, mw)
    progress.setWindowTitle("AI Language Explainer Batch Processing")
    
    # Fix for Qt6 compatibility - use Qt.WindowModality.ApplicationModal instead of Qt.WindowModal
    try:
        # Try Qt6 style enum first
        progress.setWindowModality(Qt.WindowModality.ApplicationModal) 
    except AttributeError:
        # Fallback to Qt5 style for backwards compatibility
        try:
            progress.setWindowModality(Qt.ApplicationModal)
        except:
            # Last resort fallback - don't set modality if both approaches fail
            debug_log("Failed to set window modality - Qt version compatibility issue")
            
    progress.setMinimumWidth(400)  # Set fixed width to avoid resizing issue
    progress.setValue(0)
    progress.show()
    
    # Process notes in a separate thread to keep UI responsive
    def process_notes_thread():
        success_count = 0
        skipped_count = 0
        error_count = 0
        missing_fields_count = 0
        
        try:
            for i, note_id in enumerate(selected_notes):
                if progress.wasCanceled():
                    break
                
                note = mw.col.get_note(note_id)
                
                # Update progress UI from main thread
                mw.taskman.run_on_main(lambda i=i, total=len(selected_notes): 
                    progress.setLabelText(f"Processing card {i+1} of {total}..."))
                mw.taskman.run_on_main(lambda i=i: progress.setValue(i+1))
                
                # Skip processing if note type doesn't match configured type
                model_name = note.note_type()["name"]
                if model_name != CONFIG["note_type"]:
                    debug_log(f"Skipping note {note_id}: Note type {model_name} doesn't match configured type {CONFIG['note_type']}")
                    missing_fields_count += 1
                    continue
                
                # Skip processing if required fields are missing
                required_fields = [CONFIG["word_field"], CONFIG["sentence_field"]]
                if not all(field in note and field in note.keys() for field in required_fields):
                    debug_log(f"Skipping note {note_id}: Missing required fields")
                    missing_fields_count += 1
                    continue
                
                # Process the note with separate generation flags
                success, message = process_note(note, generate_text, generate_audio, override_text, override_audio, progress_callback=None)
                if success:
                    # Check for different skip messages that were updated
                    if "already exists" in message or "not requested" in message:
                        skipped_count += 1
                        debug_log(f"Note {note_id} skipped: {message}")
                    else:
                        success_count += 1
                        debug_log(f"Note {note_id} processed successfully: {message}")
                        # Save changes to the database
                        note.flush()
                else:
                    error_count += 1
                    debug_log(f"Note {note_id} failed: {message}")
            
            # Final update on main thread
            mw.taskman.run_on_main(lambda: progress.setValue(len(selected_notes) + 1))
            
            # Show results
            mw.taskman.run_on_main(lambda: 
                showInfo(f"Batch processing complete:\n"
                         f"{success_count} cards processed successfully\n"
                         f"{skipped_count} cards skipped (already had content)\n"
                         f"{missing_fields_count} cards skipped (missing fields or wrong note type)\n"
                         f"{error_count} cards failed"))
            
        except Exception as e:
            debug_log(f"Error in batch processing: {str(e)}")
            debug_log(traceback.format_exc())
            mw.taskman.run_on_main(lambda: 
                showInfo(f"Error in batch processing: {str(e)}"))
        finally:
            mw.taskman.run_on_main(lambda: progress.hide())
    
    # Start processing thread
    threading.Thread(target=process_notes_thread, daemon=True).start()


def setup_browser_menu(browser):
    debug_log("Setting up browser menu for batch processing")
    
    # Test if we can access the menu
    if hasattr(browser.form, 'menuEdit'):
        debug_log("Browser has menuEdit attribute")
    else:
        debug_log("Browser does NOT have menuEdit attribute - trying alternative approach")
        # Backwards compatibility with different Anki versions
        try:
            # Try to find the Edit menu by name
            for menu in browser.form.menubar.findChildren(QMenu):
                if menu.title() == "Edit":
                    debug_log("Found Edit menu by title")
                    action = QAction("Batch Generate AI Explanations", browser)
                    qconnect(action.triggered, batch_process_notes)
                    menu.addSeparator()
                    menu.addAction(action)
                    debug_log("Action added to Edit menu found by title")
                    return
        except Exception as e:
            debug_log(f"Error finding Edit menu: {str(e)}")
    
    # Original implementation
    try:
        action = QAction("Batch Generate AI Explanations", browser)
        qconnect(action.triggered, batch_process_notes)
        browser.form.menuEdit.addSeparator()
        browser.form.menuEdit.addAction(action)
        debug_log("Browser menu setup complete")
    except Exception as e:
        debug_log(f"Error setting up browser menu: {str(e)}")
        
        # Try adding to a different menu as fallback
        try:
            debug_log("Trying to add to Tools menu instead")
            action = QAction("Batch Generate AI Explanations", browser)
            qconnect(action.triggered, batch_process_notes)
            browser.form.menuTools.addSeparator()
            browser.form.menuTools.addAction(action)
            debug_log("Added action to Tools menu as fallback")
        except Exception as e2:
            debug_log(f"Error adding to Tools menu: {str(e2)}")


__all__ = [
    "setup_menu",
    "open_settings",
    "batch_process_notes",
    "setup_browser_menu",
]
