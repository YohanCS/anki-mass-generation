"""Reviewer integration helpers (buttons, hooks, and card processing)."""

from __future__ import annotations

import threading
import time
import traceback

from aqt import mw
from aqt.qt import QApplication, QDialog, QMessageBox, QProgressDialog, QTimer, Qt
from aqt.utils import tooltip

from .config import CONFIG
from .logging import debug_log
from .processing import process_note
from .ui.bulk_dialog import BulkGenerationDialog


def process_current_card():
    try:
        if mw.state != "review" or not mw.reviewer.card:
            tooltip("No card is being reviewed.")
            return
        
        card = mw.reviewer.card
        note = card.note()
        
        # Create a progress dialog with a visible progress bar
        progress = QProgressDialog("Initializing...", "Cancel", 0, 100, mw)
        progress.setWindowTitle("AI Language Explainer")
        progress.setMinimumDuration(0)  # Show immediately
        progress.setAutoClose(False)    # Don't close automatically
        progress.setAutoReset(False)    # Don't reset automatically
        
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
                
        progress.setMinimumWidth(400)   # Set a fixed minimum width to prevent resizing issues
        progress.setValue(0)
        progress.setLabelText("Checking note type...")
        progress.show()  # Explicitly show the dialog
        
        # Process UI events to ensure dialog is displayed
        QApplication.processEvents()
        
        # Check note type (updated for Anki 25+)
        model_name = note.note_type()["name"]
        if model_name != CONFIG["note_type"]:
            progress.cancel()
            tooltip(f"Current card is not a {CONFIG['note_type']} note.")
            return
        
        progress.setValue(20)
        progress.setLabelText("Checking existing content...")
        QApplication.processEvents()
        
        # Check if explanation already exists
        explanation_exists = CONFIG["explanation_field"] in note and note[CONFIG["explanation_field"]].strip()
        audio_exists = CONFIG["explanation_audio_field"] in note and note[CONFIG["explanation_audio_field"]].strip()
        
        # Show the generation options dialog  
        generation_dialog = BulkGenerationDialog(mw, [note.id])
        generation_dialog.setWindowTitle("AI Language Explainer - Generation Options")
        if generation_dialog.exec() != QDialog.DialogCode.Accepted:
            debug_log("User canceled generation dialog")
            progress.cancel()
            return
        
        # Get the generation options from the dialog (4 values: generate_text, generate_audio, override_text, override_audio)
        generate_text, generate_audio, override_text, override_audio = generation_dialog.get_generation_options()
        debug_log(f"Generation options: generate_text={generate_text}, generate_audio={generate_audio}, override_text={override_text}, override_audio={override_audio}")
        
        # Store generation flags for backend processing
        CONFIG["generate_text"] = generate_text
        CONFIG["generate_audio"] = generate_audio
        CONFIG["override_text"] = override_text
        CONFIG["override_audio"] = override_audio
        
        # Proceed directly to voicevox status check
        progress.setValue(30)
        progress.setLabelText("Checking VOICEVOX status...")
        QApplication.processEvents()
        
        progress.setValue(40)
        progress.setLabelText("Generating explanation with OpenAI...")
        QApplication.processEvents()
        
        # Set up a watchdog timer to detect if processing gets stuck
        processing_timeout = 60  # seconds
        processing_start_time = time.time()
        processing_completed = [False]  # Use a list to allow modification in nested functions
        timer = [None]  # Store the timer in a list to access it from nested functions
        
        # Create a timer to check if processing is taking too long
        def check_timeout():
            if not processing_completed[0]:
                elapsed_time = time.time() - processing_start_time
                if elapsed_time > processing_timeout:
                    debug_log(f"Processing timeout after {elapsed_time:.1f} seconds")
                    mw.taskman.run_on_main(lambda: handle_timeout())
                    # Stop the timer
                    if timer[0]:
                        timer[0].stop()
            else:
                # Stop the timer once processing is completed
                if timer[0]:
                    timer[0].stop()
        
        def handle_timeout():
            try:
                if not processing_completed[0] and progress and not progress.wasCanceled():
                    progress.cancel()
                    error_dialog = QMessageBox(mw)
                    error_dialog.setIcon(QMessageBox.Icon.Warning)
                    error_dialog.setWindowTitle("Processing Timeout")
                    error_dialog.setText("The operation is taking longer than expected.")
                    error_dialog.setInformativeText("The process might be stuck. Check the error logs for details.")
                    error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
                    error_dialog.exec()
            except Exception as e:
                debug_log(f"Error in handle_timeout: {str(e)}")
        
        # Start the timeout checker using QTimer
        timer[0] = QTimer(mw)
        timer[0].timeout.connect(check_timeout)
        timer[0].start(5000)  # Check every 5 seconds
        
        # Process the note in a separate thread to keep UI responsive
        def process_with_progress():
            try:
                # Create a callback function to update the progress dialog
                def update_progress(message):
                    # Update progress value based on the stage of processing
                    progress_value = 40
                    if "Sending request to OpenAI" in message:
                        progress_value = 50
                    elif "Received explanation from OpenAI" in message:
                        progress_value = 70
                        debug_log(f"Progress update: {message}, value: {progress_value}")
                    elif "explanation saved to note" in message:
                        progress_value = 75
                        debug_log(f"Progress update: {message}, value: {progress_value}")
                    elif "Generating audio" in message:
                        progress_value = 80
                        debug_log(f"Progress update: {message}, value: {progress_value}")
                    elif "Audio generated" in message:
                        progress_value = 90
                        debug_log(f"Progress update: {message}, value: {progress_value}")
                    elif "Audio generation failed" in message or "Error generating audio" in message:
                        progress_value = 85
                        debug_log(f"Progress update: {message}, value: {progress_value}")
                    elif "VOICEVOX not running" in message:
                        progress_value = 85
                        debug_log(f"Progress update: {message}, value: {progress_value}")
                    elif "Saving changes" in message:
                        progress_value = 95
                        debug_log(f"Progress update: {message}, value: {progress_value}")
                    elif "Changes saved successfully" in message:
                        progress_value = 98
                        debug_log(f"Progress update: {message}, value: {progress_value}")
                    
                    # Force UI update on main thread
                    def update_ui():
                        update_progress_ui(message, progress_value)
                    mw.taskman.run_on_main(update_ui)
                
                def update_progress_ui(message, value):
                    try:
                        if progress.wasCanceled():
                            debug_log("Progress dialog was canceled, skipping update")
                            return
                            
                        progress.setValue(value)
                        progress.setLabelText(message)
                        QApplication.processEvents()
                        debug_log(f"UI updated: {message}, value: {value}")
                    except Exception as e:
                        debug_log(f"Error updating progress UI: {str(e)}")
                
                # Call process_note with the progress callback
                debug_log("Starting process_note with progress callback")
                result, message = process_note(note, generate_text, generate_audio, override_text, override_audio, update_progress)
                debug_log(f"process_note completed with result: {result}, message: {message}")
                
                # Mark processing as completed to stop the timeout checker
                processing_completed[0] = True
                
                # Update UI on the main thread
                mw.taskman.run_on_main(lambda: handle_process_result(result, message, card, progress))
            except Exception as e:
                # Mark processing as completed to stop the timeout checker
                processing_completed[0] = True
                
                error_msg = str(e)
                debug_log(f"Error in process_with_progress: {str(e)}")
                mw.taskman.run_on_main(lambda: 
                    show_error(error_msg, progress))
        
        # Function to handle the result on the main thread
        def handle_process_result(success, message, card, progress):
            try:
                if success:
                    progress.setValue(100)
                    progress.setLabelText("Refreshing card...")
                    QApplication.processEvents()
                    try:
                        card.load()  # Refresh the card to show new content
                        progress.cancel()
                        tooltip("explanation generated successfully!")
                    except Exception as e:
                        debug_log(f"Error in card.load(): {str(e)}")
                        progress.cancel()
                        tooltip("explanation generated, but failed to refresh card.")
                else:
                    progress.cancel()
                    error_dialog = QMessageBox(mw)
                    error_dialog.setIcon(QMessageBox.Icon.Critical)
                    error_dialog.setWindowTitle("Error")
                    error_dialog.setText("Failed to generate explanation")
                    error_dialog.setInformativeText(message)
                    error_dialog.setDetailedText(f"Please check the error log for more details.\n\nError: {message}")
                    error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
                    error_dialog.exec()
            except Exception as e:
                debug_log(f"Error in handle_process_result: {str(e)}")
                try:
                    progress.cancel()
                except:
                    pass
                tooltip("An error occurred while handling the result.")
        
        # Function to show error on the main thread
        def show_error(error_msg, progress):
            try:
                progress.cancel()
                error_dialog = QMessageBox(mw)
                error_dialog.setIcon(QMessageBox.Icon.Critical)
                error_dialog.setWindowTitle("Error")
                error_dialog.setText("Failed to generate explanation")
                error_dialog.setInformativeText(f"Error: {error_msg}")
                error_dialog.setDetailedText(f"Please check the error log for more details.\n\nError: {error_msg}")
                error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
                error_dialog.exec()
            except Exception as e:
                debug_log(f"Error in show_error: {str(e)}")
                tooltip(f"Error: {error_msg}")
        
        # Start processing in a separate thread
        threading.Thread(target=process_with_progress).start()
        
    except Exception as e:
        debug_log(f"Unexpected error in process_current_card: {str(e)}")
        tooltip("An error occurred. Check the error log for details.")


def add_button_to_reviewer():
    try:
        debug_log("Adding button to reviewer")
        
        # Get reviewer bottombar element
        bottombar = mw.reviewer.bottom.web
        
        # Create JavaScript code to add button
        js = """
        (function() {
            console.log('Running AI Language Explainer button script');
            
            // Check if the button already exists
            if (document.getElementById('gpt-button')) {
                console.log('Button already exists, skipping');
                return;
            }
            
            // Create the button
            var button = document.createElement('button');
            button.id = 'gpt-button';
            button.className = 'btn';
            button.style.margin = '5px';
            button.style.padding = '6px 12px';
            button.style.fontSize = '14px';
            button.style.cursor = 'pointer';
            button.style.backgroundColor = '#4CAF50';
            button.style.color = 'white';
            button.style.border = 'none';
            button.style.borderRadius = '4px';
            button.style.boxShadow = '0 2px 5px rgba(0,0,0,0.2)';
            
            button.innerText = 'Generate explanation';
            
            // Set up the click handler with debugging
            button.onclick = function() {
                console.log('Generate explanation button clicked');
                pycmd('gpt_explanation');
                return false;
            };
            
            // Create a fixed position container at the top of the screen
            var buttonContainer = document.createElement('div');
            buttonContainer.id = 'gpt-button-container';
            buttonContainer.style.position = 'fixed';
            buttonContainer.style.top = '10px';
            buttonContainer.style.left = '25%';
            buttonContainer.style.transform = 'translateX(-50%)';
            buttonContainer.style.zIndex = '9999';
            buttonContainer.style.textAlign = 'center';
            buttonContainer.style.backgroundColor = 'rgba(240, 240, 240, 0.9)';
            buttonContainer.style.padding = '5px 10px';
            buttonContainer.style.borderRadius = '5px';
            buttonContainer.style.boxShadow = '0 2px 8px rgba(0,0,0,0.2)';
            
            buttonContainer.appendChild(button);
            
            // Add to the document body
            document.body.appendChild(buttonContainer);
            
            console.log('AI Language Explainer button added successfully');
        })();
        """
        
        # Inject JavaScript code
        bottombar.eval(js)
        debug_log("JavaScript injected to add button")
    except Exception as e:
        debug_log(f"Error adding button to reviewer: {str(e)}")
        debug_log(traceback.format_exc())


def on_card_shown(card=None):
    try:
        # Log for debugging
        debug_log(f"on_card_shown called with card: {card}")
        
        # Check if button is hidden in settings
        if CONFIG.get("hide_button", False):
            debug_log("Button is hidden in settings, skipping button addition")
            return
        
        # Only add the button when the answer is shown
        if mw.state != "review":
            debug_log("Not in review state, skipping button addition")
            return
            
        if not mw.reviewer.card:
            debug_log("No card in reviewer, skipping button addition")
            return
            
        if not mw.reviewer.state == "answer":
            debug_log("Not showing answer, skipping button addition")
            return
        
        # Use the card parameter if provided, otherwise fall back to mw.reviewer.card
        current_card = card if card else mw.reviewer.card
        debug_log(f"Current card ID: {current_card.id}")
        
        # Get the note type
        note_type_name = current_card.note().note_type()["name"]
        debug_log(f"Note type: {note_type_name}, Config note type: {CONFIG['note_type']}")
        
        if note_type_name == CONFIG["note_type"]:
            debug_log("Note type matches, adding button")
            add_button_to_reviewer()
        else:
            debug_log(f"Note type doesn't match, skipping button addition")
    except Exception as e:
        debug_log(f"Error in on_card_shown: {str(e)}")
        debug_log(traceback.format_exc())


def on_js_message(handled, message, context):
    # Log the message for debugging
    debug_log(f"Received message: {message}, handled: {handled}, context: {context}")
    
    # In Anki 25, the message might be a tuple or a string
    cmd = None
    if isinstance(message, tuple):
        cmd = message[0]
    else:
        cmd = message
    
    # Check if this is our command
    if cmd == "gpt_explanation":
        debug_log("Recognized gpt_explanation command, processing...")
        process_current_card()
        
        # Try to detect Anki version to return appropriate value
        try:
            import anki
            anki_version = int(anki.buildinfo.version.split('.')[0])
            debug_log(f"Anki version: {anki_version}")
            if anki_version >= 25:
                debug_log("Returning (True, None) for Anki 25+")
                return (True, None)
            else:
                debug_log("Returning True for older Anki")
                return True
        except Exception as e:
            debug_log(f"Error detecting Anki version: {e}")
            # If we can't determine version, return a tuple which works in Anki 25
            return (True, None)
    
    return handled


__all__ = [
    "process_current_card",
    "add_button_to_reviewer",
    "on_card_shown",
    "on_js_message",
]
