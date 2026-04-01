# File: api_handler.py
import os
import requests
import json
import base64
import re
import time
import sys
import traceback
from aqt import mw
from urllib.request import urlopen
from urllib.parse import unquote
import subprocess
import platform

timeout_seconds = 60

# Debug logging
def debug_log(message):
    """Write debug messages to a separate log file"""
    try:
        addon_dir = os.path.dirname(os.path.abspath(__file__))
        debug_log_path = os.path.join(addon_dir, "debug_log.txt")
        
        with open(debug_log_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception as e:
        print(f"Failed to write to debug log: {e}")

# OpenAI API Endpoints
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

# OpenAI API
def process_with_openai(api_key, prompt, model="gpt-4.1"):
    """
    Process the prompt with OpenAI's API and return the explanation
    
    Parameters:
    - api_key: OpenAI API key
    - prompt: The prompt to send to GPT
    - model: The OpenAI model to use
    
    Returns:
    - str: The explanation from GPT
    """
    debug_log("=== PROCESS WITH OPENAI START ===")
    debug_log(f"Prompt: {prompt}")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # Prepare the messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant for language learners."},
        {"role": "user", "content": prompt}
    ]
    
    # gpt-5.x models require max_completion_tokens; older models use max_tokens
    tokens_key = "max_completion_tokens" if model.startswith("gpt-5") else "max_tokens"
    data = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        tokens_key: 500,
    }
    
    try:
        debug_log("Sending request to OpenAI API...")
        response = requests.post(OPENAI_CHAT_URL, headers=headers, json=data, timeout=timeout_seconds)
        debug_log(f"Response status code: {response.status_code}")

        if response.status_code != 200:
            error_details = response.text[:500] if response.text else "No error details"
            debug_log(f"API returned error status: {response.status_code}")
            debug_log(f"Response text: {error_details}")

            # Try to parse error message from response
            try:
                error_json = response.json()
                if 'error' in error_json:
                    error_msg = error_json['error'].get('message', error_details)
                    raise Exception(f"OpenAI API Error (HTTP {response.status_code}): {error_msg}")
            except (json.JSONDecodeError, KeyError):
                pass

            raise Exception(f"OpenAI API Error (HTTP {response.status_code}): {error_details}")

        response.raise_for_status()

        try:
            response_data = response.json()
            debug_log("Successfully parsed JSON response")
        except json.JSONDecodeError as e:
            error_text = response.text[:500] if response.text else "No response text"
            debug_log(f"Error parsing JSON response: {str(e)}")
            debug_log(f"Response text: {error_text}")
            raise Exception(f"Failed to parse OpenAI response: {str(e)}. Response: {error_text}")

        if 'choices' in response_data and len(response_data['choices']) > 0:
            explanation = response_data['choices'][0]['message']['content']
            debug_log(f"Received explanation, length: {len(explanation)}")
            debug_log(f"Explanation first 100 chars: {explanation[:100]}...")
            debug_log("=== PROCESS WITH OPENAI COMPLETE ===")
            return explanation
        else:
            debug_log("Response missing 'choices' or empty choices array")
            debug_log(f"Response data: {str(response_data)[:500]}...")
            raise Exception(f"Invalid OpenAI response: Missing 'choices' in response. Data: {str(response_data)[:200]}")
    except requests.exceptions.Timeout:
        debug_log("Timeout while calling OpenAI API")
        raise Exception(f"OpenAI API timeout after {timeout_seconds} seconds")
    except requests.exceptions.ConnectionError as e:
        debug_log(f"Connection error calling OpenAI API: {str(e)}")
        raise Exception(f"Failed to connect to OpenAI API: {str(e)}")
    except requests.exceptions.RequestException as e:
        debug_log(f"Request error calling OpenAI API: {str(e)}")
        raise Exception(f"OpenAI API request failed: {str(e)}")
    except Exception as e:
        # Re-raise our own exceptions, wrap others
        if "OpenAI API" in str(e) or "Failed to parse" in str(e) or "Invalid OpenAI" in str(e):
            raise
        debug_log(f"Unexpected error calling OpenAI API: {str(e)}")
        debug_log(f"Stack trace: {traceback.format_exc()}")
        raise Exception(f"Unexpected error calling OpenAI: {str(e)}")
    finally:
        debug_log("=== PROCESS WITH OPENAI END ===")

def check_voicevox_running():
    """
    Check if VOICEVOX server is running
    
    Returns:
    - bool: True if VOICEVOX server is running, False otherwise
    """
    try:
        debug_log("Checking if VOICEVOX is running...")
        
        # Try multiple URLs to check if VOICEVOX is running
        test_urls = [
            "http://localhost:50021/version",  # Standard URL
            "http://127.0.0.1:50021/version",  # Alternative localhost
            "http://0.0.0.0:50021/version"     # Another alternative
        ]
        
        for url in test_urls:
            try:
                debug_log(f"Trying to connect to VOICEVOX at {url}")
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    debug_log(f"VOICEVOX is running at {url}, version: {response.text}")
                    return True
                else:
                    debug_log(f"VOICEVOX at {url} returned non-200 status code: {response.status_code}")
            except requests.exceptions.ConnectionError:
                debug_log(f"VOICEVOX connection error at {url} - server not running")
            except requests.exceptions.Timeout:
                debug_log(f"VOICEVOX connection timeout at {url}")
            except Exception as e:
                debug_log(f"Error checking VOICEVOX at {url}: {str(e)}")
        
        # If we get here, all URLs failed
        debug_log("All VOICEVOX connection attempts failed")
        return False
    except Exception as e:
        debug_log(f"Unexpected error in check_voicevox_running: {str(e)}")
        return False

def check_aivisspeech_running(base_url="http://127.0.0.1:10101"):
    """
    Check if AivisSpeech server is running
    
    Parameters:
    - base_url: The base URL for the AivisSpeech engine (e.g., http://127.0.0.1:10101)

    Returns:
    - bool: True if AivisSpeech server is running, False otherwise
    """
    try:
        debug_log(f"Checking if AivisSpeech is running at {base_url}...")
        # AivisSpeech uses /speakers endpoint, similar to VoiceVox's /version or /speakers
        # We can also check /docs as per their documentation
        test_endpoints = ["/speakers", "/docs"]
        
        for endpoint in test_endpoints:
            url = f"{base_url.rstrip('/')}{endpoint}"
            try:
                debug_log(f"Trying to connect to AivisSpeech at {url}")
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    debug_log(f"AivisSpeech is running at {url}. Status: {response.status_code}")
                    return True
                else:
                    debug_log(f"AivisSpeech at {url} returned non-200 status code: {response.status_code}")
            except requests.exceptions.ConnectionError:
                debug_log(f"AivisSpeech connection error at {url} - server not running or wrong port.")
            except requests.exceptions.Timeout:
                debug_log(f"AivisSpeech connection timeout at {url}")
            except Exception as e:
                debug_log(f"Error checking AivisSpeech at {url}: {str(e)}")
        
        debug_log(f"All AivisSpeech connection attempts to {base_url} failed")
        return False
    except Exception as e:
        debug_log(f"Unexpected error in check_aivisspeech_running: {str(e)}")
        return False

# ElevenLabs TTS generation
def generate_audio_elevenlabs(api_key, text, voice_id):
    """Generate audio using ElevenLabs TTS."""
    debug_log("=== ELEVENLABS AUDIO GENERATION START ===")
    if not api_key or not voice_id or not text:
        debug_log("Missing api_key, voice_id, or text for ElevenLabs TTS")
        return None
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }
        payload = {
            "text": text, 
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
        debug_log(f"Sending ElevenLabs request: voice_id={voice_id}, text length={len(text)}")
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
        debug_log(f"ElevenLabs status: {response.status_code}")
        if response.status_code != 200:
            debug_log(f"ElevenLabs error: {response.text[:200]}")
            return None
        # Save audio to media directory
        media_dir = os.path.join(mw.pm.profileFolder(), "collection.media")
        os.makedirs(media_dir, exist_ok=True)
        timestamp = int(time.time())
        filename = f"elevenlabs_tts_{voice_id}_{timestamp}.mp3"
        file_path = os.path.join(media_dir, filename)
        with open(file_path, "wb") as f:
            f.write(response.content)
        debug_log(f"Written ElevenLabs audio file: {file_path}")
        return file_path
    except Exception as e:
        debug_log(f"Exception in ElevenLabs TTS: {e}")
        return None
    finally:
        debug_log("=== ELEVENLABS AUDIO GENERATION END ===")

# OpenAI TTS generation
def generate_audio_openai_tts(api_key, text, voice, speed=1.0):
    """Generate audio using OpenAI TTS endpoint."""
    debug_log("=== OPENAI TTS GENERATION START ===")
    if not api_key or not text or not voice:
        debug_log("Missing api_key, voice, or text for OpenAI TTS")
        return None
    try:
        url = "https://api.openai.com/v1/audio/speech"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {"model": "tts-1", "voice": voice, "input": text, "speed": speed}
        debug_log(f"Sending OpenAI TTS request: model=tts-1, voice={voice}, speed={speed}, input length={len(text)}")
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
        debug_log(f"OpenAI TTS status: {response.status_code}")
        if response.status_code != 200:
            debug_log(f"OpenAI TTS error: {response.text[:200]}")
            return None
        # Save audio to media directory
        media_dir = os.path.join(mw.pm.profileFolder(), "collection.media")
        os.makedirs(media_dir, exist_ok=True)
        timestamp = int(time.time())
        filename = f"openai_tts_{voice}_{timestamp}.mp3"
        file_path = os.path.join(media_dir, filename)
        with open(file_path, "wb") as f:
            f.write(response.content)
        debug_log(f"Written OpenAI TTS audio file: {file_path}")
        return f"[sound:{filename}]"
    except Exception as e:
        debug_log(f"Exception in OpenAI TTS: {e}")
        return None
    finally:
        debug_log("=== OPENAI TTS GENERATION END ===")

# AivisSpeech TTS voices
def get_aivisspeech_voices(base_url="http://127.0.0.1:10101"):
    """
    Fetch available voices (speakers and styles) from AivisSpeech engine.

    Parameters:
    - base_url: The base URL for the AivisSpeech engine.

    Returns:
    - list: A list of voice dictionaries, e.g., 
            [{'speaker_name': 'Speaker A', 'style_name': 'Normal', 'style_id': 123}, ...]
            Returns None if an error occurs.
    """
    debug_log(f"Fetching AivisSpeech voices from {base_url}...")
    voices_list = []
    try:
        speakers_url = f"{base_url.rstrip('/')}/speakers"
        response = requests.get(speakers_url, timeout=5)
        response.raise_for_status() # Raise an exception for HTTP errors
        speakers_data = response.json()
        
        if not isinstance(speakers_data, list):
            debug_log(f"AivisSpeech /speakers endpoint did not return a list. Data: {speakers_data}")
            return None

        for speaker in speakers_data:
            speaker_name = speaker.get('name', 'Unknown Speaker')
            if 'styles' in speaker and isinstance(speaker['styles'], list):
                for style in speaker['styles']:
                    style_name = style.get('name', 'Default Style')
                    style_id = style.get('id')
                    if style_id is not None:
                        voices_list.append({
                            'speaker_name': speaker_name,
                            'style_name': style_name,
                            'style_id': style_id
                        })
        debug_log(f"Found {len(voices_list)} AivisSpeech voices.")
        return voices_list
    except requests.exceptions.Timeout:
        debug_log(f"AivisSpeech: Timeout fetching voices from {base_url}")
        return None
    except requests.exceptions.RequestException as e:
        debug_log(f"AivisSpeech: Request error fetching voices: {str(e)}")
        return None
    except json.JSONDecodeError as e:
        debug_log(f"AivisSpeech: Error decoding JSON from /speakers: {str(e)}")
        return None
    except Exception as e:
        debug_log(f"AivisSpeech: Unexpected error fetching voices: {str(e)}")
        return None

# AivisSpeech TTS generation
def generate_audio_aivisspeech(text, style_id=None, base_url="http://127.0.0.1:10101", save_to_collection=True):
    debug_log(f"=== AUDIO GENERATION START (AivisSpeech at {base_url}) ===")
    debug_log(f"Text length: {len(text) if text else 'None'}, Style ID: {style_id}, Save to collection: {save_to_collection}")

    if not text or len(text.strip()) == 0:
        debug_log("Empty text provided for AivisSpeech, cannot generate audio")
        return None

    max_text_length = 500
    if len(text) > max_text_length:
        debug_log(f"AivisSpeech: Text too long ({len(text)} chars), truncating to {max_text_length} chars")
        text = text[:max_text_length] + "..."

    try:
        if not check_aivisspeech_running(base_url):
            debug_log(f"AivisSpeech engine not running or not accessible at {base_url}. Aborting audio generation.")
            return None

        if style_id is None:
            # Fallback to fetching the first available style_id if not provided
            # This might be needed for the main generation if no voice is explicitly configured yet
            debug_log("AivisSpeech: style_id not provided, attempting to find a default.")
            voices = get_aivisspeech_voices(base_url)
            if voices and len(voices) > 0:
                style_id = voices[0]['style_id']
                debug_log(f"AivisSpeech: Using first available style_id: {style_id}")
            else:
                debug_log("AivisSpeech: Could not find any voices to determine a default style_id.")
                return None
        
        query_url = f"{base_url.rstrip('/')}/audio_query"
        query_params = {"text": text, "speaker": style_id}
        debug_log(f"AivisSpeech: Requesting audio query from {query_url} with params: {query_params}")
        response = requests.post(query_url, params=query_params, timeout=timeout_seconds)    
        response.raise_for_status()
        audio_query_data = response.json()
        debug_log("AivisSpeech: Received audio query.")

        synthesis_url = f"{base_url.rstrip('/')}/synthesis"
        synthesis_params = {"speaker": style_id}
        headers = {"Content-Type": "application/json"}
        debug_log(f"AivisSpeech: Requesting synthesis from {synthesis_url} with params: {synthesis_params}")
        response = requests.post(synthesis_url, params=synthesis_params, json=audio_query_data, headers=headers, timeout=timeout_seconds)
        response.raise_for_status()
        audio_data = response.content
        debug_log(f"AivisSpeech: Received audio data, length: {len(audio_data)} bytes.")

        if save_to_collection:
            timestamp = int(time.time())
            filename = f"aivis_speech_{style_id}_{timestamp}.wav"
            media_dir = os.path.join(mw.pm.profileFolder(), "collection.media")
            if not os.path.exists(media_dir):
                os.makedirs(media_dir)
            filepath = os.path.join(media_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(audio_data)
            debug_log(f"AivisSpeech: Audio saved to collection: {filepath}")
            return f"[sound:{filename}]" # Return Anki sound tag for collection items
        else:
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_file.write(audio_data)
            temp_file.close()
            debug_log(f"AivisSpeech: Audio saved to temporary file: {temp_file.name}")
            return temp_file.name # Return direct filepath for temporary samples

    except requests.exceptions.Timeout:
        debug_log(f"AivisSpeech: Timeout during API call to {base_url}")
        return None
    except requests.exceptions.RequestException as e:
        debug_log(f"AivisSpeech: Request error during API call to {base_url}: {str(e)}")
        return None
    except Exception as e:
        debug_log(f"AivisSpeech: Unexpected error during audio generation: {str(e)}")
        debug_log(f"Stack trace for AivisSpeech error: {traceback.format_exc()}")
        return None
    finally:
        debug_log("=== AUDIO GENERATION END (AivisSpeech) ===")

# Qwen3-TTS generation
def generate_audio_qwen3(text, model="Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", voice_prompt="高音萝莉女声，音调偏高且起伏明显，语气活泼可爱，带有轻微撒娇感"):
    """
    Generate audio using Qwen3-TTS running in a separate Python venv.

    Anki uses Python 3.9 which is too old for qwen-tts/PyTorch, so this
    function calls out to a small helper script via subprocess using the
    venv Python the user set up during installation.

    Returns:
    - str|None: Anki sound tag "[sound:filename.wav]", or None on failure.
    """
    debug_log("=== QWEN3-TTS AUDIO GENERATION START ===")
    if not text or not text.strip():
        debug_log("Qwen3-TTS: Empty text, aborting.")
        return None

    try:
        import uuid
        import subprocess
        import sys
        from . import CONFIG

        # ── Find the venv Python ──────────────────────────────────────────
        # First check if the user has set a custom path in config,
        # otherwise fall back to common locations.
        venv_python = CONFIG.get("qwen3_python_path", "")

        if not venv_python or not os.path.isfile(venv_python):
            # Try the default location from the setup guide
            candidates = [
                r"C:\Github\qwen-tts\qwen-tts-env\Scripts\python.exe",
                os.path.join(os.path.expanduser("~"), "qwen-tts-env", "Scripts", "python.exe"),
                os.path.join(os.path.expanduser("~"), "Github", "qwen-tts", "qwen-tts-env", "Scripts", "python.exe"),
            ]
            for candidate in candidates:
                if os.path.isfile(candidate):
                    venv_python = candidate
                    debug_log(f"Qwen3-TTS: Auto-detected venv Python at: {venv_python}")
                    break

        if not venv_python or not os.path.isfile(venv_python):
            debug_log("Qwen3-TTS: Could not find venv Python. Set 'qwen3_python_path' in config.")
            raise Exception(
                "Qwen3-TTS: venv Python not found.\n\n"
                "Please add 'qwen3_python_path' to your add-on config pointing to your "
                "qwen-tts-env Python, e.g.:\n"
                r"C:\Github\qwen-tts\qwen-tts-env\Scripts\python.exe"
            )

        # ── Save text and prompt to temp files to avoid shell escaping issues ─
        import tempfile
        media_dir = os.path.join(mw.pm.profileFolder(), "collection.media")
        os.makedirs(media_dir, exist_ok=True)
        filename = f"qwen3tts_{uuid.uuid4().hex[:12]}.wav"
        output_path = os.path.join(media_dir, filename)

        # Inline helper script — no separate file needed on disk
        helper_script = f"""
import sys, torch, soundfile as sf
from qwen_tts import Qwen3TTSModel

model_name = {repr(model)}
voice_prompt = {repr(voice_prompt)}
text = {repr(text)}
output_path = {repr(output_path)}

# Cache model between calls using a module-level attribute
if not hasattr(sys, "_qwen3_model_cache"):
    sys._qwen3_model_cache = {{}}

if model_name not in sys._qwen3_model_cache:
    sys._qwen3_model_cache[model_name] = Qwen3TTSModel.from_pretrained(
        model_name,
        device_map="cuda:0",
        dtype=torch.bfloat16,
    )

m = sys._qwen3_model_cache[model_name]
wavs, sr = m.generate_voice_design(
    text=[text],
    language=["Chinese"],
    instruct=[voice_prompt],
)
sf.write(output_path, wavs[0], sr)
print("OK:" + output_path)
"""

        debug_log(f"Qwen3-TTS: Calling venv Python: {venv_python}")
        debug_log(f"Qwen3-TTS: Model={model}, output={output_path}")

        result = subprocess.run(
            [venv_python, "-c", helper_script],
            capture_output=True,
            text=True,
            timeout=300,  # 5 min — first run loads model weights
        )

        if result.returncode != 0:
            debug_log(f"Qwen3-TTS: subprocess failed (rc={result.returncode})")
            debug_log(f"Qwen3-TTS stderr: {result.stderr[-1000:]}")
            raise Exception(f"Qwen3-TTS subprocess error:\n{result.stderr[-500:]}")

        debug_log(f"Qwen3-TTS: subprocess stdout: {result.stdout.strip()}")

        if os.path.isfile(output_path) and os.path.getsize(output_path) > 100:
            debug_log(f"Qwen3-TTS: Audio saved successfully: {output_path}")
            return f"[sound:{filename}]"
        else:
            debug_log("Qwen3-TTS: Output file missing or too small after subprocess.")
            return None

    except subprocess.TimeoutExpired:
        debug_log("Qwen3-TTS: subprocess timed out (>5 min).")
        raise Exception("Qwen3-TTS timed out. The model may still be downloading — try again in a few minutes.")
    except Exception as e:
        debug_log(f"Qwen3-TTS: Error: {str(e)}")
        debug_log(traceback.format_exc())
        raise
    finally:
        debug_log("=== QWEN3-TTS AUDIO GENERATION END ===")


# VoiceVox TTS generation
def generate_audio_voicevox(text, style_id=None):
    """
    Generate audio using VOICEVOX engine.

    Parameters:
    - text (str): The text to synthesize.
    - style_id (int|None): Preferred VoiceVox style identifier to use.

    Returns:
    - str|None: The file path to the generated .wav audio file, or None if generation failed.
    """
    debug_log("=== VOICEVOX AUDIO GENERATION START ===")
    if not text or len(text.strip()) == 0:
        debug_log("VOICEVOX: Empty text provided, cannot generate audio.")
        return None

    # Limit text length as VOICEVOX has input limits
    max_text_length = 500  # This limit can be adjusted based on VOICEVOX's capabilities
    if len(text) > max_text_length:
        debug_log(f"VOICEVOX: Text too long ({len(text)} chars), truncating to {max_text_length} chars.")
        text = text[:max_text_length] + "..."

    try:
        # Quick accessibility check for the VOICEVOX server
        debug_log("VOICEVOX: Performing quick accessibility check.")
        try:
            response = requests.get("http://localhost:50021/version", timeout=1) # Short timeout for check
            if response.status_code != 200:
                debug_log(f"VOICEVOX: Server not accessible or non-200 status: {response.status_code}.")
                return None
            debug_log(f"VOICEVOX: Server accessible, version: {response.text}.")
        except Exception as e:
            debug_log(f"VOICEVOX: Initial server check failed: {str(e)}.")
            return None
        
        # Determine the media directory for saving the audio file
        media_dir = os.path.join(mw.pm.profileFolder(), "collection.media")
        debug_log(f"VOICEVOX: Media directory set to: {media_dir}.")

        # Ensure the media directory exists and is writable
        if not os.path.exists(media_dir):
            debug_log(f"VOICEVOX: Media directory does not exist, attempting to create: {media_dir}.")
            try:
                os.makedirs(media_dir, exist_ok=True)
                debug_log(f"VOICEVOX: Media directory created: {media_dir}.")
            except Exception as e:
                debug_log(f"VOICEVOX: Failed to create media directory: {str(e)}.")
                return None
        
        # Verify writability (optional, but good for diagnostics)
        # test_file_path = os.path.join(media_dir, "voicevox_writability_test.tmp")
        # try:
        #     with open(test_file_path, 'w') as f: f.write("test")
        #     os.remove(test_file_path)
        #     debug_log("VOICEVOX: Media directory confirmed writable.")
        # except Exception as e:
        #     debug_log(f"VOICEVOX: Media directory not writable: {str(e)}.")
        #     return None

        # Generate a unique filename using a hash of the text and a timestamp
        file_hash = base64.b16encode(text.encode('utf-8')).decode('utf-8')[:16].lower()
        timestamp = int(time.time())
        filename = f"voicevox_audio_{file_hash}_{timestamp}.wav"
        file_path = os.path.join(media_dir, filename)
        debug_log(f"VOICEVOX: Target audio file path: {file_path}.")

        # Use the provided style id if available, otherwise fall back to a sensible default
        speaker_id = style_id if style_id is not None else 11
        timeout_seconds = 60 # Increased timeout slightly for synthesis

        # Step 1: Create an audio query
        # This step converts text to an intermediate representation used by VOICEVOX.
        debug_log("VOICEVOX: Creating audio query...")
        query_params = {'text': text, 'speaker': speaker_id}
        try:
            query_response = requests.post('http://localhost:50021/audio_query', params=query_params)
            query_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            audio_query_json = query_response.json()
            debug_log("VOICEVOX: Audio query created successfully.")
        except requests.exceptions.Timeout:
            debug_log("VOICEVOX: Timeout during audio query creation.")
            return None
        except requests.exceptions.RequestException as e:
            debug_log(f"VOICEVOX: Error during audio query request: {str(e)}.")
            return None
        except json.JSONDecodeError as e:
            debug_log(f"VOICEVOX: Error decoding audio query JSON response: {str(e)}. Response text: {query_response.text[:200]}")
            return None

        # Step 2: Synthesize audio from the query
        # This step takes the intermediate representation and generates the actual WAV audio data.
        debug_log("VOICEVOX: Synthesizing audio data...")
        synthesis_params = {'speaker': speaker_id}
        try:
            synthesis_response = requests.post('http://localhost:50021/synthesis', params=synthesis_params, json=audio_query_json, timeout=timeout_seconds)
            synthesis_response.raise_for_status()
            audio_data = synthesis_response.content
            debug_log(f"VOICEVOX: Audio data synthesized, size: {len(audio_data)} bytes.")
        except requests.exceptions.Timeout:
            debug_log("VOICEVOX: Timeout during audio synthesis.")
            return None
        except requests.exceptions.RequestException as e:
            debug_log(f"VOICEVOX: Error during audio synthesis request: {str(e)}.")
            return None

        if len(audio_data) < 100: # Basic check for valid audio data
            debug_log(f"VOICEVOX: Synthesized audio data is too small ({len(audio_data)} bytes), likely an error.")
            return None

        # Step 3: Save the audio data to a file
        debug_log(f"VOICEVOX: Saving audio data to file: {file_path}")
        try:
            with open(file_path, 'wb') as f:
                f.write(audio_data)
            
            # Verify file creation and size
            if os.path.exists(file_path) and os.path.getsize(file_path) > 100:
                debug_log(f"VOICEVOX: Audio file successfully saved: {file_path}, size: {os.path.getsize(file_path)} bytes.")
                return file_path # Return the full path to the audio file
            else:
                debug_log("VOICEVOX: Audio file not found or too small after attempting to save.")
                return None
        except Exception as e:
            debug_log(f"VOICEVOX: Error writing audio file: {str(e)}.")
            return None
            
    except Exception as e:
        debug_log(f"VOICEVOX: Unexpected error in generate_audio_voicevox: {str(e)}.")
        debug_log(f"Stack trace for VOICEVOX error: {traceback.format_exc()}")
        return None
    finally:
        debug_log("=== VOICEVOX AUDIO GENERATION END ===")

# This is the main audio generation dispatcher
def generate_audio(api_key, text, engine_override=None, style_id_override=None, speaker_id_override=None, save_to_collection_override=None, qwen3_model=None, qwen3_voice_prompt=None):
    """
    Dispatch to the selected TTS engine and generate audio.
    Can be overridden for specific cases like sample generation.
    """
    from . import CONFIG  # import CONFIG here to avoid circular import
    
    engine = engine_override if engine_override else CONFIG.get("tts_engine", "VoiceVox")
    save_to_collection = save_to_collection_override if save_to_collection_override is not None else True
    
    # Debug log the parameters being used for this call
    debug_log(f"generate_audio called with: engine='{engine}', save_to_collection={save_to_collection}, style_id_override={style_id_override}, text_length={len(text) if text else 0}")

    if engine == "ElevenLabs":
        return generate_audio_elevenlabs(CONFIG.get("elevenlabs_key", ""), text, CONFIG.get("elevenlabs_voice_id", ""))
    if engine == "OpenAI TTS":
        speed = CONFIG.get("openai_tts_speed", 1.0)
        return generate_audio_openai_tts(api_key, text, CONFIG.get("openai_tts_voice", "alloy"), speed)
    if engine == "AivisSpeech":
        # Use style_id_override if provided (for samples), else use configured default, else fallback in generate_audio_aivisspeech
        current_aivis_style_id = style_id_override if style_id_override is not None else CONFIG.get("aivisspeech_style_id")
        # The generate_audio_aivisspeech function itself has a fallback if current_aivis_style_id is None
        return generate_audio_aivisspeech(text, style_id=current_aivis_style_id, save_to_collection=save_to_collection)
    if engine == "VoiceVox":
        current_voicevox_style_id = style_id_override if style_id_override is not None else CONFIG.get("voicevox_style_id")
        # Preserve compatibility with older callers that still pass speaker_id_override
        if current_voicevox_style_id is None and speaker_id_override is not None:
            current_voicevox_style_id = speaker_id_override
        return generate_audio_voicevox(text, current_voicevox_style_id)
    if engine == "Qwen3-TTS":
        model = qwen3_model or CONFIG.get("qwen3_tts_model", "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign")
        voice_prompt = qwen3_voice_prompt or CONFIG.get("qwen3_tts_voice_prompt", "高音萝莉女声，音调偏高且起伏明显，语气活泼可爱，带有轻微撒娇感")
        return generate_audio_qwen3(text, model=model, voice_prompt=voice_prompt)
    
    # If engine is not recognized or no specific handler, log and return None
    debug_log(f"Unknown or unhandled TTS engine: {engine}. Cannot generate audio.")
    return None