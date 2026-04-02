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
        "Please write an explanation of the word '{word}' using the context of "
        "the original sentence: '{sentence}'. {word} and {sentence} are in Chinese "
        "so do not write {word} or {sentence} in the response as it will be incorrectly voiced.\n\n"
        "Return your response in exactly this format with XML tags — no other text outside the tags:\n\n"
        "<ja>Write a Japanese explanation here. Explain the core meaning of the word and how it is "
        "used in this sentence. Write for a Japanese native around 13 years old, like explaining to a friend. "
        "Start with the core meaning, then explain how it appears in the sentence. "
        "DO NOT use English. DO NOT write furigana in brackets. DO NOT start with introductory phrases "
        "like という言葉を簡単に説明するね — dive straight in. Katakana words are fine if natives use them.</ja>\n\n"
        "<zh>Write a Chinese (Mandarin) explanation of the same word here, for a native Chinese speaker "
        "around 13 years old. Explain the meaning and usage naturally in Chinese. "
        "DO NOT use English or Japanese.</zh>\n\n"
        "<en>Write a concise English definition of the word here — just the meaning, no preamble.</en>"
    ),

    # === TTS/Audio Generation Settings ===
    "tts_engine": "OpenAI TTS",
    "elevenlabs_key": "",
    "elevenlabs_voice_id": "",
    "openai_tts_voice": "alloy",
    "openai_tts_speed": 1.0,
    "aivisspeech_style_id": None,
    "voicevox_style_id": None,

    # === Multilingual Audio Fields ===
    # Set these to field names in your note type, or leave blank to skip that language
    "explanation_audio_zh_field": "AI Audio ZH",
    "explanation_audio_ja_field": "AI Audio JP",
    "explanation_audio_en_field": "AI Audio EN",

    # === Qwen3-TTS Settings ===
    "qwen3_tts_model": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "qwen3_python_path": "",  # e.g. C:\Github\qwen-tts\qwen-tts-env\Scripts\python.exe

    # Per-language voice prompts for Qwen3-TTS
    "qwen3_voice_prompt_zh": "高音萝莉女声，音调偏高且起伏明显，语气活泼可爱，带有轻微撒娇感",
    "qwen3_voice_prompt_ja": "明るく自然な日本語女性の声、標準的なアクセント、アニメキャラクターらしい話し方",
    "qwen3_voice_prompt_en": "Bright and clear young female voice, natural English pronunciation, friendly anime style",

    # Legacy single-field prompt kept for backward compat with non-multilingual mode
    "qwen3_tts_voice_prompt": "高音萝莉女声，音调偏高且起伏明显，语气活泼可爱，带有轻微撒娇感",

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