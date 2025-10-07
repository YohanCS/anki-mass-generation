"""Note processing routines for AI Language Explainer."""

from __future__ import annotations

import os
import traceback
from .config import CONFIG
from .logging import debug_log
from ..api_handler import generate_audio as backend_generate_audio, process_with_openai


def process_note_debug(note, generate_text, generate_audio, override_text, override_audio, progress_callback=None):
    """
    Process a note to generate text explanations and/or audio based on user preferences.
    
    This function implements a 4-checkbox system:
    1. generate_text: Whether user wants to generate explanation text
    2. generate_audio: Whether user wants to generate explanation audio  
    3. override_text: Whether to override existing explanation text (only shown if content exists)
    4. override_audio: Whether to override existing explanation audio (only shown if content exists)
    
    Logic Flow:
    - Text is generated if: user wants it AND (field is empty OR override requested) AND feature not disabled
    - Audio is generated if: user wants it AND (field is empty OR override requested) AND feature not disabled
    - If nothing needs generation, the function exits early with appropriate reasoning
    
    Args:
        note: The Anki note to process
        generate_text: Boolean - whether to generate explanation text
        generate_audio: Boolean - whether to generate explanation audio
        override_text: Boolean - whether to override existing explanation text
        override_audio: Boolean - whether to override existing explanation audio  
        progress_callback: Optional function to call with progress updates
        
    Returns:
        tuple: (success: bool, message: str) indicating result and details
    """
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    debug_log_path = os.path.join(addon_dir, "process_debug.txt")
    
    debug_log("=== PROCESS NOTE START ===")
    debug_log(f"Note ID: {note.id}")
    
    try:
        if not CONFIG["openai_key"]:
            debug_log("No API key set")
            return False, "No OpenAI API key set. Please set your API key in the settings."

        # Extract data from note
        debug_log("Extracting data from note")
        word = note[CONFIG["word_field"]] if CONFIG["word_field"] in note else ""
        sentence = note[CONFIG["sentence_field"]] if CONFIG["sentence_field"] in note else ""
        definition = ""
        debug_log(f"Word field: {CONFIG['word_field']} = {word[:30]}...")
        debug_log(f"Sentence field: {CONFIG['sentence_field']} = {sentence[:30]}...")
        
        # Check if text generation is disabled in settings
        text_generation_disabled = CONFIG.get("disable_text_generation", False)
        debug_log(f"Text generation disabled: {text_generation_disabled}")
        
        # === STEP 1: Check current field states ===
        # Check what content currently exists in the target fields
        explanation_exists = CONFIG["explanation_field"] in note and note[CONFIG["explanation_field"]].strip()
        audio_exists = CONFIG["explanation_audio_field"] in note and note[CONFIG["explanation_audio_field"]].strip()
        
        debug_log(f"=== FIELD STATE ANALYSIS ===")
        debug_log(f"Explanation field '{CONFIG['explanation_field']}' exists: {explanation_exists}")
        debug_log(f"Audio field '{CONFIG['explanation_audio_field']}' exists: {audio_exists}")
        
        # === STEP 2: Log user's checkbox selections ===
        debug_log(f"=== USER CHECKBOX SELECTIONS ===")
        debug_log(f"Generate Text checkbox: {generate_text}")
        debug_log(f"Generate Audio checkbox: {generate_audio}")  
        debug_log(f"Override Text checkbox: {override_text}")
        debug_log(f"Override Audio checkbox: {override_audio}")
        
        # === STEP 3: Check system settings ===
        debug_log(f"=== SYSTEM SETTINGS ===")
        debug_log(f"Text generation disabled: {text_generation_disabled}")
        debug_log(f"Audio generation disabled: {CONFIG.get('disable_audio', False)}")
        
        # === STEP 4: Determine what should be generated ===
        # 
        # Core Logic for Generation Decision:
        # For each content type (text/audio), we generate if ALL three conditions are met:
        # 1. User wants generation (checkbox checked)
        # 2. Content is needed (field is empty OR user explicitly wants to override existing content)
        # 3. Feature is allowed (not disabled in settings)
        #
        # This ensures that:
        # - Empty fields get auto-generated when user requests generation
        # - Existing content is preserved unless user explicitly chooses to override
        # - Disabled features are respected regardless of user choices
        debug_log(f"=== GENERATION DECISION LOGIC ===")
        
        # Text decision breakdown
        text_user_wants = generate_text  # Did user check "Generate Text"?
        text_needed = not explanation_exists or override_text  # Is text needed? (empty OR override requested)
        text_allowed = not text_generation_disabled  # Is text generation enabled in settings?
        should_generate_text = text_user_wants and text_needed and text_allowed
        
        debug_log(f"TEXT DECISION:")
        debug_log(f"  User wants text generation: {text_user_wants}")
        debug_log(f"  Text needed (empty field OR override requested): {text_needed}")
        debug_log(f"    - Field is empty: {not explanation_exists}")
        debug_log(f"    - Override requested: {override_text}")
        debug_log(f"  Text generation allowed (not disabled): {text_allowed}")
        debug_log(f"  FINAL TEXT DECISION: {should_generate_text}")
        
        # Audio decision breakdown  
        audio_user_wants = generate_audio  # Did user check "Generate Audio"?
        audio_needed = not audio_exists or override_audio  # Is audio needed? (empty OR override requested)
        audio_allowed = not CONFIG.get("disable_audio", False)  # Is audio generation enabled in settings?
        should_generate_audio = audio_user_wants and audio_needed and audio_allowed
        
        debug_log(f"AUDIO DECISION:")
        debug_log(f"  User wants audio generation: {audio_user_wants}")
        debug_log(f"  Audio needed (empty field OR override requested): {audio_needed}")
        debug_log(f"    - Field is empty: {not audio_exists}")
        debug_log(f"    - Override requested: {override_audio}")
        debug_log(f"  Audio generation allowed (not disabled): {audio_allowed}")
        debug_log(f"  FINAL AUDIO DECISION: {should_generate_audio}")
        
        # === STEP 5: Early exit check ===
        debug_log(f"=== EARLY EXIT CHECK ===")
        if not should_generate_text and not should_generate_audio:
            debug_log("EARLY EXIT: Nothing to generate")
            debug_log(f"Reason: should_generate_text={should_generate_text}, should_generate_audio={should_generate_audio}")
            
            # Provide more specific feedback about why nothing was generated
            reasons = []
            if not text_user_wants and not audio_user_wants:
                reasons.append("no generation requested")
            elif text_generation_disabled and CONFIG.get("disable_audio", False):
                reasons.append("both text and audio generation disabled in settings")
            elif explanation_exists and not override_text and audio_exists and not override_audio:
                reasons.append("content already exists and no override requested")
            elif explanation_exists and not override_text:
                reasons.append("text content already exists and text override not requested")
            elif audio_exists and not override_audio:
                reasons.append("audio content already exists and audio override not requested")
            else:
                reasons.append("generation conditions not met")
            
            reason_text = ", ".join(reasons)
            debug_log(f"Early exit reason: {reason_text}")
            return True, f"Skipped: {reason_text}"
        
        debug_log(f"PROCEEDING: At least one type of generation is needed")
        debug_log(f"Will generate text: {should_generate_text}")
        debug_log(f"Will generate audio: {should_generate_audio}")
        
        # Process with OpenAI (only if text generation is needed)
        explanation = None
        if should_generate_text:
            debug_log("Text generation needed - preparing prompt for OpenAI")
            try:
                prompt = CONFIG["gpt_prompt"].format(
                    word=word,
                    sentence=sentence,
                    definition=definition
                )
            except KeyError as e:
                debug_log(f"KeyError in prompt formatting: {str(e)}")
                debug_log(f"Prompt template: {CONFIG['gpt_prompt']}")
                debug_log(f"Available variables: word='{word}', sentence='{sentence}', definition='{definition}'")
                return False, f"Error in prompt template: missing placeholder {str(e)}"
            
            debug_log("Calling process_with_openai")
            try:
                if progress_callback and callable(progress_callback):
                    progress_callback("Sending request to OpenAI...")

                explanation = process_with_openai(CONFIG["openai_key"], prompt, CONFIG["openai_model"])
                debug_log(f"Received explanation: {explanation[:50]}...")

                if progress_callback and callable(progress_callback):
                    progress_callback("Received explanation from OpenAI")
            except Exception as e:
                debug_log(f"Error in process_with_openai: {str(e)}")
                return False, str(e)
        else:
            debug_log("Text generation not needed - using existing content for audio generation")
            # Use existing explanation for audio generation if available
            if CONFIG["explanation_field"] in note and note[CONFIG["explanation_field"]].strip():
                explanation = note[CONFIG["explanation_field"]]
                debug_log("Using existing explanation text for audio generation")
            else:
                # Use word for audio generation if no explanation exists
                explanation = word if word else "テスト"
                debug_log(f"No existing explanation, using word for audio: {explanation}")
            
            if progress_callback and callable(progress_callback):
                progress_callback("Using existing content for audio generation")
        
        # Save explanation to note (only if text generation was performed and we have new content)
        if should_generate_text and CONFIG["explanation_field"] in note:
            debug_log(f"Saving newly generated explanation to field: {CONFIG['explanation_field']}")
            try:
                note[CONFIG["explanation_field"]] = explanation
                debug_log("Newly generated explanation saved to note")
                
                if progress_callback and callable(progress_callback):
                    progress_callback("Explanation saved to note")
            except Exception as e:
                debug_log(f"Error setting explanation field: {CONFIG['explanation_field']}: {str(e)}")
                return False, f"Error saving explanation to note: {str(e)}"
        elif not should_generate_text:
            debug_log("Text generation not performed, skipping explanation field update")
        
        # Also try the "explanation" field (with correct spelling) if it exists (only if text generation was performed)
        if should_generate_text and "explanation" in note and CONFIG["explanation_field"] != "explanation":
            debug_log("Also saving newly generated explanation to 'explanation' field (correct spelling)")
            try:
                note["explanation"] = explanation
                debug_log("Explanation saved to note (correct spelling field)")
            except Exception as e:
                debug_log(f"Error setting explanation field (correct spelling): {str(e)}")
                # Continue even if this fails
        
        # Audio generation using the selected TTS engine
        debug_log("Starting audio generation step")
        audio_path_result = [None]
        audio_error = None

        # Check if audio generation should be performed
        if should_generate_audio:
            debug_log("Audio generation needed - proceeding with TTS")
            # Only generate if the audio field exists
            if CONFIG["explanation_audio_field"] in note:
                debug_log(f"Audio field found: {CONFIG['explanation_audio_field']}")
                try:
                    # Update progress callback
                    if progress_callback and callable(progress_callback):
                        progress_callback(f"Generating audio with {CONFIG['tts_engine']}...")
                    # Generate audio using the explanation text (existing or newly generated)
                    debug_log(f"Calling generate_audio with engine: {CONFIG['tts_engine']}")
                    debug_log(f"Audio generation parameters: api_key_length={len(CONFIG.get('openai_key', ''))}, explanation_length={len(explanation)}")

                    # Prepare parameters for audio generation with detailed logging
                    api_key = CONFIG.get("openai_key", "")
                    aivis_style_id = CONFIG.get("aivisspeech_style_id") if CONFIG['tts_engine'] == 'AivisSpeech' else None
                    voicevox_style_id = CONFIG.get("voicevox_style_id") if CONFIG['tts_engine'] == 'VoiceVox' else None

                    debug_log(
                        f"Calling generate_audio with: api_key='{api_key[:10] if api_key else 'None'}...', "
                        f"text_length={len(explanation)}, aivis_style_id={aivis_style_id}, "
                        f"voicevox_style_id={voicevox_style_id}"
                    )

                    selected_style_override = aivis_style_id if aivis_style_id is not None else voicevox_style_id

                    audio_path = backend_generate_audio(
                        api_key,
                        explanation,
                        style_id_override=selected_style_override
                    )
                    if audio_path:
                        debug_log(f"Audio generated successfully: {audio_path}")
                        audio_path_result[0] = audio_path
                    else:
                        audio_error = f"{CONFIG['tts_engine']} audio generation failed: No audio file returned"
                        debug_log(audio_error)
                except Exception as e:
                    audio_error = f"{CONFIG['tts_engine']} audio generation error: {str(e)}"
                    debug_log(f"Error during audio generation: {str(e)}")

                # Save audio result to note if generation was successful
                if audio_path_result[0]:
                    # If the returned value is already an Anki sound tag, use it as-is,
                    # otherwise wrap the filename in one. This prevents double "[sound:" tags
                    if str(audio_path_result[0]).startswith("[sound:") and str(audio_path_result[0]).endswith("]"):
                        note[CONFIG["explanation_audio_field"]] = audio_path_result[0]
                    else:
                        audio_filename = os.path.basename(audio_path_result[0])
                        note[CONFIG["explanation_audio_field"]] = f"[sound:{audio_filename}]"
                    debug_log("Audio reference saved to note")
                else:
                    # Audio generation failed - add placeholder and prepare to return error
                    note[CONFIG["explanation_audio_field"]] = "[Audio generation failed]"
                    debug_log("Audio generation failed, placeholder saved")
            else:
                audio_error = f"Audio field '{CONFIG['explanation_audio_field']}' not found in note"
                debug_log(audio_error)
        
        elif CONFIG.get("disable_audio", False):
            debug_log("Audio generation is disabled in settings - leaving audio field unchanged")
            # Don't modify the audio field when audio generation is disabled
        else:
            debug_log("Audio generation not needed - leaving audio field unchanged")
            # Don't modify the audio field when audio override is not requested
        
        # Also handle the "explanationAudio" field (with correct spelling) if it exists
        if should_generate_audio and "explanationAudio" in note and CONFIG["explanation_audio_field"] != "explanationAudio":
            debug_log("Also updating 'explanationAudio' field (correct spelling)")
            if audio_path_result[0]:
                # If the returned value is already an Anki sound tag, use it as-is,
                # otherwise wrap the filename in one. This prevents double "[sound:" tags
                if str(audio_path_result[0]).startswith("[sound:") and str(audio_path_result[0]).endswith("]"):
                    note["explanationAudio"] = audio_path_result[0]
                else:
                    audio_filename = os.path.basename(audio_path_result[0])
                    note["explanationAudio"] = f"[sound:{audio_filename}]"
                debug_log("Audio reference saved to explanationAudio field (correct spelling)")
            else:
                note["explanationAudio"] = "[Audio generation failed]"
                debug_log("Audio generation failed, setting placeholder in explanationAudio field")
        
        # Save changes - wrap in try/except to catch any issues
        try:
            debug_log("Calling note.flush() to save changes")

            if progress_callback and callable(progress_callback):
                progress_callback("Saving changes to note...")

            note.flush()
            debug_log("Note.flush() completed successfully")

            if progress_callback and callable(progress_callback):
                progress_callback("Changes saved successfully")
        except Exception as e:
            debug_log(f"Error in note.flush(): {str(e)}")
            return False, f"Error saving changes to note: {str(e)}"

        # Check if audio generation failed when it was requested
        if audio_error:
            debug_log(f"=== PROCESS NOTE COMPLETED WITH AUDIO ERROR ===")
            return False, audio_error

        debug_log("=== PROCESS NOTE COMPLETED SUCCESSFULLY ===")
        return True, "Process completed successfully"
    except Exception as e:
        debug_log(f"Unexpected error in process_note: {str(e)}")
        debug_log(f"Stack trace: {traceback.format_exc()}")
        return False, f"Unexpected error: {str(e)}"

# Replace the original process_note function with the debug version
process_note = process_note_debug


__all__ = ["process_note", "process_note_debug"]
