"""Configuration helpers for the AI Language Explainer add-on."""

from __future__ import annotations

import json
import os
from typing import Dict, List

from aqt import mw

from .logging import debug_log


_ADDON_MODULE_NAME: str | None = None


CONFIG: Dict[str, object] = {
    # === Note Configuration ===
    "note_type": "",
    "word_field": "",
    "sentence_field": "",
    "explanation_field": "",
    "explanation_audio_field": "",

    # === OpenAI/Text Generation Settings ===
    "openai_key": "",
    "openai_model": "gpt-4.1",
    "gpt_prompt": (
        "Please write a short explanation of the word '{word}' using the context of "
        "the original sentence: '{sentence}'. Write an explanation that helps a "
        "Japanese beginner understand the word and how it is used with this context "
        "as an example. Explain it in the same way a native would explain it to a "
        "child. Don't use any English, only use simpler Japanese. Don't write the "
        "furigana for any of the words in brackets after the word. Don't start with "
        "stuff like という言葉を簡単に説明するね, just dive straight into explaining after "
        "starting with the word."
    ),

    # === TTS/Audio Generation Settings ===
    "tts_engine": "OpenAI TTS",
    "elevenlabs_key": "",
    "elevenlabs_voice_id": "",
    "openai_tts_voice": "alloy",
    "openai_tts_speed": 1.0,
    "aivisspeech_style_id": None,
    "voicevox_style_id": None,

    # === Qwen3-TTS Settings ===
    "qwen3_tts_model": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "qwen3_tts_voice_prompt": "高音萝莉女声，音调偏高且起伏明显，语气活泼可爱，带有轻微撒娇感",
    "qwen3_python_path": "",  # e.g. C:\Github\qwen-tts\qwen-tts-env\Scripts\python.exe

    # === Feature Toggles & UI Preferences ===
    "disable_text_generation": False,
    "disable_audio": False,
    "hide_button": False,
}


def set_addon_module_name(module_name: str) -> None:
    """Record the root module name so config writes target the correct add-on."""

    global _ADDON_MODULE_NAME
    _ADDON_MODULE_NAME = module_name


def _module_name() -> str:
    if _ADDON_MODULE_NAME:
        return _ADDON_MODULE_NAME
    return __name__.split(".")[0]


def load_config() -> None:
    """Load configuration from meta.json and the Anki add-on config store."""

    addon_dir = os.path.dirname(os.path.abspath(__file__))
    addon_root = os.path.dirname(addon_dir)

    defaults = {}
    try:
        with open(os.path.join(addon_root, "meta.json"), encoding="utf-8") as meta_file:
            meta = json.load(meta_file)
            defaults = meta.get("config", {}) or {}
    except Exception:
        pass

    user = mw.addonManager.getConfig(_module_name()) or {}

    rename_map = {
        "explaination_field": "explanation_field",
        "explaination_audio_field": "explanation_audio_field",
        "elevenlabs_api_key": "elevenlabs_key",
        "voicevox_default_speaker_id": "voicevox_style_id",
    }
    for old_key, new_key in rename_map.items():
        if old_key in user and new_key not in user:
            user[new_key] = user.pop(old_key)

    for key, default_value in defaults.items():
        if key in user:
            if isinstance(default_value, str):
                CONFIG[key] = user[key] if user[key] else default_value
            else:
                CONFIG[key] = user[key]
        else:
            CONFIG[key] = default_value

    for key, value in user.items():
        if key not in defaults:
            CONFIG[key] = value

    debug_log(f"Final merged config: {CONFIG}")


def save_config() -> None:
    """Persist CONFIG to Anki's add-on manager."""

    mw.addonManager.writeConfig(_module_name(), CONFIG)


def get_note_types() -> List[str]:
    """Return all available note type names (Anki 25+ compatible)."""

    return [model["name"] for model in mw.col.models.all()]


def get_fields_for_note_type(note_type_name: str) -> List[str]:
    """Return the list of fields for a given note type name."""

    for model in mw.col.models.all():
        if model["name"] == note_type_name:
            return [field["name"] for field in model["flds"]]

    return []


__all__ = [
    "CONFIG",
    "set_addon_module_name",
    "load_config",
    "save_config",
    "get_note_types",
    "get_fields_for_note_type",
]