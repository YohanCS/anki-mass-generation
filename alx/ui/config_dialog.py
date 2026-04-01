"""Settings dialog for configuring the AI Language Explainer add-on."""

from __future__ import annotations

import os
import requests
import webbrowser

from aqt import mw
from aqt.qt import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    Qt,
)
from aqt.utils import qconnect

from ..config import (
    CONFIG,
    get_fields_for_note_type,
    get_note_types,
    load_config,
    save_config,
)
from ..logging import debug_log
from ...api_handler import (
    generate_audio as backend_generate_audio,
    check_aivisspeech_running,
    check_voicevox_running,
    get_aivisspeech_voices,
)


class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super(ConfigDialog, self).__init__(parent)
        self.setWindowTitle("AI Language Explainer Settings")
        self.setMinimumWidth(500) # Set a minimum width for the dialog
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        # Tab 1: Note & Field Configuration
        note_field_tab = QWidget()
        layout = QVBoxLayout(note_field_tab) # Use 'layout' for this tab's content

        layout.addWidget(QLabel("<b>Note & Field Configuration</b>"))
         
        # Note Type selection
        note_type_layout = QHBoxLayout()
        note_type_layout.addWidget(QLabel("Note Type:"))
        self.note_type_combo = QComboBox()
        self.note_type_combo.addItems(get_note_types())
        qconnect(self.note_type_combo.currentIndexChanged, self.update_field_combos)
        note_type_layout.addWidget(self.note_type_combo)
        layout.addLayout(note_type_layout)

        # Field selection combos
        layout.addWidget(QLabel("<b>Input Fields</b>")) # Added heading
        word_field_layout = QHBoxLayout()
        word_field_layout.addWidget(QLabel("Word Field: {word}"))
        self.word_field_combo = QComboBox()
        word_field_layout.addWidget(self.word_field_combo)
        layout.addLayout(word_field_layout)
        sentence_field_layout = QHBoxLayout()
        sentence_field_layout.addWidget(QLabel("Sentence Field: {sentence}"))
        self.sentence_field_combo = QComboBox()
        sentence_field_layout.addWidget(self.sentence_field_combo)
        layout.addLayout(sentence_field_layout)
        
        layout.addWidget(QLabel("<b>Output Fields</b>")) # Added heading
        explanation_field_layout = QHBoxLayout()
        explanation_field_layout.addWidget(QLabel("Explanation Field:"))
        self.explanation_field_combo = QComboBox()
        explanation_field_layout.addWidget(self.explanation_field_combo)
        layout.addLayout(explanation_field_layout)
        audio_field_layout = QHBoxLayout()
        audio_field_layout.addWidget(QLabel("Explanation Audio Field:"))
        self.explanation_audio_field_combo = QComboBox()
        audio_field_layout.addWidget(self.explanation_audio_field_combo)
        layout.addLayout(audio_field_layout)
        # Verification label for field selection
        self.field_verification_label = QLabel()
        layout.addWidget(self.field_verification_label)
        layout.addStretch() # Add stretch to push content to the top
        tab_widget.addTab(note_field_tab, "Note & Fields")

        # Tab 2: UI Preferences
        ui_prefs_tab = QWidget()
        layout = QVBoxLayout(ui_prefs_tab) # Reuse 'layout' for this tab's content

        layout.addWidget(QLabel("<b>UI Preferences</b>"))
        
        # Checkbox for hiding the button
        self.hide_button_checkbox = QCheckBox("Hide 'Generate explanation' button during review")
        layout.addWidget(self.hide_button_checkbox)
        layout.addStretch() # Add stretch
        tab_widget.addTab(ui_prefs_tab, "UI Preferences")
        
        # Tab 3: Text Generation
        text_gen_tab = QWidget()
        layout = QVBoxLayout(text_gen_tab) # Reuse 'layout' for this tab's content

        layout.addWidget(QLabel("<b>Text Generation</b>"))
        
        # Checkbox for disabling text generation
        self.disable_text_generation_checkbox = QCheckBox("Disable text generation")
        layout.addWidget(self.disable_text_generation_checkbox)
        qconnect(self.disable_text_generation_checkbox.toggled, self.update_text_generation_panels)
        
        # Create a container widget for the text generation settings
        self.text_generation_settings_widget = QWidget()
        text_gen_layout = QVBoxLayout(self.text_generation_settings_widget)
        text_gen_layout.setContentsMargins(0, 0, 0, 0)
        
        text_key_layout = QHBoxLayout()
        text_key_layout.addWidget(QLabel("OpenAI API Key:"))
        self.openai_key = QLineEdit()
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        text_key_layout.addWidget(self.openai_key)
        self.text_key_validate_btn = QPushButton("Validate Key")
        qconnect(self.text_key_validate_btn.clicked, self.validate_openai_key)
        text_key_layout.addWidget(self.text_key_validate_btn)
        text_gen_layout.addLayout(text_key_layout)
        
        # Model selection dropdown
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.model_dropdown = QComboBox()
        self.model_dropdown.addItems([
            "gpt-5.4",
            "gpt-5.4-mini",
            "gpt-5.4-nano",
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4.1-nano", 
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-3.5-turbo"
        ])
        self.model_dropdown.setCurrentText("gpt-5.4")
        model_layout.addWidget(self.model_dropdown)
        model_layout.addStretch()
        text_gen_layout.addLayout(model_layout)
        
        # Model recommendation text
        model_recommendation = QLabel("gpt-5.4 is recommended SIKE lol")
        model_recommendation.setStyleSheet("font-size: 11px; color: #666; font-style: italic; margin-top: 2px;")
        model_recommendation.setWordWrap(True)
        text_gen_layout.addWidget(model_recommendation)
        text_gen_layout.addWidget(QLabel("Prompt:"))
        
        # Add reminder text above prompt box
        prompt_reminder = QLabel("Remember that {sentence} and {word} should be lowercase placeholders. It's case sensitive. There should be no other {x} in your prompt.")
        prompt_reminder.setStyleSheet("font-size: 11px; color: #666; font-style: italic; margin-top: 2px;")
        prompt_reminder.setWordWrap(True)
        text_gen_layout.addWidget(prompt_reminder)
        
        self.gpt_prompt_input = QTextEdit()
        self.gpt_prompt_input.setFixedHeight(150) # Increased height
        text_gen_layout.addWidget(self.gpt_prompt_input)
        
        layout.addWidget(self.text_generation_settings_widget)
        layout.addStretch() # Add stretch
        tab_widget.addTab(text_gen_tab, "Text Generation")

        # Tab 4: TTS Generation
        tts_gen_tab = QWidget()
        layout = QVBoxLayout(tts_gen_tab) # Reuse 'layout' for this tab's content

        layout.addWidget(QLabel("<b>TTS Generation</b>"))
        
        # Checkbox for disabling audio generation
        self.disable_audio_checkbox = QCheckBox("Disable audio generation")
        layout.addWidget(self.disable_audio_checkbox)
        qconnect(self.disable_audio_checkbox.toggled, self.update_tts_panels)
        
        # Create a container widget for the engine selection
        self.engine_selection_widget = QWidget()
        engine_layout_container = QHBoxLayout(self.engine_selection_widget) # Renamed to avoid conflict
        engine_layout_container.setContentsMargins(0, 0, 0, 0) # Remove extra margins
        engine_layout_container.addWidget(QLabel("Engine:"))
        self.tts_engine_combo = QComboBox()
        self.tts_engine_combo.addItems(["VoiceVox", "ElevenLabs", "OpenAI TTS", "AivisSpeech", "Qwen3-TTS"])
        qconnect(self.tts_engine_combo.currentIndexChanged, self.update_tts_panels)
        engine_layout_container.addWidget(self.tts_engine_combo)
        layout.addWidget(self.engine_selection_widget) # Add the container widget

        # VoiceVox subpanel
        self.panel_voicevox = QWidget()
        pv = QVBoxLayout(self.panel_voicevox)
        pv.setContentsMargins(0,0,0,0)
        self.voicevox_test_btn = QPushButton("Test VoiceVox Connection")
        qconnect(self.voicevox_test_btn.clicked, self.test_voicevox_connection)
        pv.addWidget(self.voicevox_test_btn)

        # Load Available Voices for VoiceVox
        self.voicevox_load_voices_btn = QPushButton("Load Available Voices")
        qconnect(self.voicevox_load_voices_btn.clicked, self.load_voicevox_voices_ui)
        pv.addWidget(self.voicevox_load_voices_btn)

        # Voices Table for VoiceVox
        self.voicevox_voices_table = QTableWidget()
        self.voicevox_voices_table.setColumnCount(4)
        self.voicevox_voices_table.setHorizontalHeaderLabels(["Speaker", "Style", "Play Sample", "Use as Default"])
        self.voicevox_voices_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.voicevox_voices_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.voicevox_voices_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.voicevox_voices_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.voicevox_voices_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        pv.addWidget(self.voicevox_voices_table)

        layout.addWidget(self.panel_voicevox)

        # ElevenLabs subpanel
        self.panel_elevenlabs = QWidget()
        pel = QVBoxLayout(self.panel_elevenlabs)
        pel.setContentsMargins(0,0,0,0)
        # API Key input and validation
        eleven_key_layout = QHBoxLayout()
        eleven_key_layout.addWidget(QLabel("ElevenLabs API Key:"))
        self.elevenlabs_key_input = QLineEdit()
        self.elevenlabs_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        eleven_key_layout.addWidget(self.elevenlabs_key_input)
        self.elevenlabs_validate_btn = QPushButton("Validate Key")
        qconnect(self.elevenlabs_validate_btn.clicked, self.validate_elevenlabs_key)
        eleven_key_layout.addWidget(self.elevenlabs_validate_btn)
        pel.addLayout(eleven_key_layout)

        elevenlabs_instructions = QLabel(
            "Create or manage your key at "
            "<a href=\"https://elevenlabs.io/app/developers/api-keys\">https://elevenlabs.io/app/developers/api-keys</a>. "
            "Ensure the key grants access to the text-to-speech endpoint and read access to the voices endpoint."
        )
        elevenlabs_instructions.setWordWrap(True)
        elevenlabs_instructions.setOpenExternalLinks(True)
        elevenlabs_instructions.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        pel.addWidget(elevenlabs_instructions)
        # Free-form Voice ID input
        voice_id_layout = QHBoxLayout()
        voice_id_layout.addWidget(QLabel("Voice ID:"))
        self.elevenlabs_voice_id_input = QLineEdit()
        voice_id_layout.addWidget(self.elevenlabs_voice_id_input)
        pel.addLayout(voice_id_layout)
        layout.addWidget(self.panel_elevenlabs)

        # OpenAI TTS subpanel
        self.panel_openai_tts = QWidget()
        poi = QVBoxLayout(self.panel_openai_tts)
        poi.setContentsMargins(0,0,0,0)
        
        # Voice selection row
        openai_tts_layout = QHBoxLayout()
        openai_tts_layout.addWidget(QLabel("OpenAI TTS Voice:"))
        self.openai_tts_combo = QComboBox()
        self.openai_tts_combo.addItems(["alloy","ash","ballad","coral","echo","fable","nova","onyx","sage","shimmer"])
        openai_tts_layout.addWidget(self.openai_tts_combo)
        self.openai_tts_validate_btn = QPushButton("Validate Key")
        qconnect(self.openai_tts_validate_btn.clicked, self.validate_openai_key) # Reconnect OpenAI key validation
        openai_tts_layout.addWidget(self.openai_tts_validate_btn)
        poi.addLayout(openai_tts_layout)
        
        # Speed slider row
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))
        self.openai_tts_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.openai_tts_speed_slider.setMinimum(50)  # 0.5 * 100
        self.openai_tts_speed_slider.setMaximum(300) # 3.0 * 100
        self.openai_tts_speed_slider.setValue(100)   # 1.0 * 100 (default)
        self.openai_tts_speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.openai_tts_speed_slider.setTickInterval(50)  # Ticks at 0.5, 1.0, 1.5, 2.0, 2.5, 3.0
        speed_layout.addWidget(self.openai_tts_speed_slider)
        
        # Speed value label
        self.openai_tts_speed_label = QLabel("1.0x")
        self.openai_tts_speed_label.setMinimumWidth(40)
        speed_layout.addWidget(self.openai_tts_speed_label)
        
        # Connect slider to update label
        qconnect(self.openai_tts_speed_slider.valueChanged, self.update_speed_label)
        
        poi.addLayout(speed_layout)
        layout.addWidget(self.panel_openai_tts)

        # AivisSpeech subpanel
        self.panel_aivisspeech = QWidget()
        pas = QVBoxLayout(self.panel_aivisspeech)
        pas.setContentsMargins(0,0,0,0)
        
        # Test Connection Button (kept at the top or bottom for consistency)
        self.aivisspeech_test_btn = QPushButton("Test AivisSpeech Connection")
        qconnect(self.aivisspeech_test_btn.clicked, self.test_aivisspeech_connection)
        pas.addWidget(self.aivisspeech_test_btn)

        # Load Voices Button
        self.aivisspeech_load_voices_btn = QPushButton("Load Available Voices")
        qconnect(self.aivisspeech_load_voices_btn.clicked, self.load_aivisspeech_voices_ui)
        pas.addWidget(self.aivisspeech_load_voices_btn)

        # Voices Table
        self.aivisspeech_voices_table = QTableWidget()
        self.aivisspeech_voices_table.setColumnCount(4) # Speaker, Style, Play, Set Default
        self.aivisspeech_voices_table.setHorizontalHeaderLabels(["Speaker", "Style", "Play Sample", "Use as Default"])
        self.aivisspeech_voices_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.aivisspeech_voices_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.aivisspeech_voices_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.aivisspeech_voices_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.aivisspeech_voices_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.aivisspeech_voices_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) # Make table read-only
        pas.addWidget(self.aivisspeech_voices_table)
        
        layout.addWidget(self.panel_aivisspeech)

        # Qwen3-TTS subpanel
        self.panel_qwen3_tts = QWidget()
        pq = QVBoxLayout(self.panel_qwen3_tts)
        pq.setContentsMargins(0, 0, 0, 0)

        # Info label
        qwen3_info = QLabel(
            "Qwen3-TTS runs <b>locally on your GPU</b>. Make sure you have completed the "
            "setup guide and the model is downloaded before using this engine."
        )
        qwen3_info.setWordWrap(True)
        qwen3_info.setStyleSheet("color: #888; font-style: italic; margin-bottom: 6px;")
        pq.addWidget(qwen3_info)

        # venv Python path
        python_row = QHBoxLayout()
        python_row.addWidget(QLabel("Venv Python path:"))
        self.qwen3_python_path_input = QLineEdit()
        self.qwen3_python_path_input.setPlaceholderText(
            r"C:\Github\qwen-tts\qwen-tts-env\Scripts\python.exe"
        )
        python_row.addWidget(self.qwen3_python_path_input)
        pq.addLayout(python_row)

        python_hint = QLabel(
            "Point this to the python.exe inside the venv you created during setup. "
            "Leave blank to use the auto-detected default path."
        )
        python_hint.setWordWrap(True)
        python_hint.setStyleSheet("font-size: 11px; color: #666; font-style: italic; margin-bottom: 4px;")
        pq.addWidget(python_hint)

        # Model size selection
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self.qwen3_model_combo = QComboBox()
        self.qwen3_model_combo.addItems([
            "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
            "Qwen/Qwen3-TTS-12Hz-0.6B-VoiceDesign",
        ])
        model_row.addWidget(self.qwen3_model_combo)
        model_row.addStretch()
        pq.addLayout(model_row)

        model_hint = QLabel("1.7B = better quality (needs ~6 GB VRAM). 0.6B = faster (needs ~3 GB VRAM).")
        model_hint.setStyleSheet("font-size: 11px; color: #666; font-style: italic;")
        model_hint.setWordWrap(True)
        pq.addWidget(model_hint)

        # Voice prompt
        pq.addWidget(QLabel("Voice Style Prompt (Chinese natural language description):"))
        self.qwen3_voice_prompt_input = QTextEdit()
        self.qwen3_voice_prompt_input.setFixedHeight(80)
        self.qwen3_voice_prompt_input.setPlaceholderText(
            "e.g. 高音萝莉女声，音调偏高且起伏明显，语气活泼可爱，带有轻微撒娇感"
        )
        pq.addWidget(self.qwen3_voice_prompt_input)

        prompt_hint = QLabel(
            "Describe the voice in Chinese. Examples: 冷静知性的成熟女声 (cool mature female), "
            "活泼开朗的少年男声 (energetic young male), 沉稳低沉的男性旁白 (deep calm male narrator)."
        )
        prompt_hint.setWordWrap(True)
        prompt_hint.setStyleSheet("font-size: 11px; color: #666; font-style: italic;")
        pq.addWidget(prompt_hint)

        # Test button
        self.qwen3_test_btn = QPushButton("Test Qwen3-TTS (generates a sample)")
        qconnect(self.qwen3_test_btn.clicked, self.test_qwen3_tts)
        pq.addWidget(self.qwen3_test_btn)

        layout.addWidget(self.panel_qwen3_tts)

        self.update_tts_panels() # Call once to set initial visibility
        layout.addStretch() # Add stretch
        tab_widget.addTab(tts_gen_tab, "TTS Generation")

        # Promotional section (appears on all tabs)
        promo_widget = QWidget()
        promo_layout = QVBoxLayout(promo_widget)
        promo_layout.setContentsMargins(10, 8, 10, 5)
        
        # Add minimal spacing
        promo_layout.addWidget(QLabel())  # Empty label for spacing
        
        # Promotional message
        promo_label = QLabel("If you want to learn how to reach native-level fluency as fast as possible, click the button below.")
        promo_label.setWordWrap(True)
        promo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        promo_label.setStyleSheet("font-size: 12px; color: #666; margin: 5px 0px;")
        promo_layout.addWidget(promo_label)
        
        # Promotional button
        promo_button = QPushButton("Learn Language Learning Theory")
        promo_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 4px;
                margin: 5px 0px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        qconnect(promo_button.clicked, self.open_language_learning_community)
        promo_layout.addWidget(promo_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addWidget(promo_widget)

        # Buttons (common to all tabs, so placed outside the tab_widget)
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        cancel_button = QPushButton("Cancel")
        qconnect(save_button.clicked, self.save_and_close)
        qconnect(cancel_button.clicked, self.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout) # Add buttons to the main_layout

    def update_field_combos(self):
        note_type = self.note_type_combo.currentText()
        fields = get_fields_for_note_type(note_type)
        
        # Clear and update all field comboboxes
        for combo in [self.word_field_combo, self.sentence_field_combo,
                      self.explanation_field_combo, self.explanation_audio_field_combo]:
            current_text = combo.currentText()
            combo.clear()
            combo.addItems(fields)
        
        # Verify if selected fields exist in the note type
        self.verify_fields()

    def verify_fields(self):
        """Verify if the selected fields exist in the note type and show warnings if not"""
        note_type = self.note_type_combo.currentText()
        fields = get_fields_for_note_type(note_type)
        
        missing_fields = []
        
        # Check audio field specifically since it's critical for audio generation
        audio_field = self.explanation_audio_field_combo.currentText()
        if audio_field and audio_field not in fields:
            missing_fields.append(f"'{audio_field}' (audio)")
        
        if missing_fields:
            warning = f"Warning: The following fields are not in the note type '{note_type}':<br>"
            warning += "<br>".join(missing_fields)
            warning += "<br><br>You may need to add these fields to your note type or select different fields."
            self.field_verification_label.setText(warning)
        else:
            self.field_verification_label.setText("")

    def load_settings(self):
        load_config()
        
        # Set note type selection: use configured value or default to first available
        note_types = get_note_types()
        if CONFIG["note_type"] in note_types:
            self.note_type_combo.setCurrentText(CONFIG["note_type"])
        else:
            if note_types:
                self.note_type_combo.setCurrentIndex(0)
                CONFIG["note_type"] = note_types[0]
        # Update field combos based on selected note type
        self.update_field_combos()
        
        # Set field values
        field_combos = {
            "word_field": self.word_field_combo,
            "sentence_field": self.sentence_field_combo,
            "explanation_field": self.explanation_field_combo,
            "explanation_audio_field": self.explanation_audio_field_combo
        }
        
        for field_name, combo in field_combos.items():
            if CONFIG[field_name] and CONFIG[field_name] in [combo.itemText(i) for i in range(combo.count())]:
                combo.setCurrentText(CONFIG[field_name])
        
        # Load Text Generation settings
        self.openai_key.setText(CONFIG["openai_key"])
        self.model_dropdown.setCurrentText(CONFIG["openai_model"])
        self.gpt_prompt_input.setPlainText(CONFIG["gpt_prompt"])
        
        # Load TTS settings
        self.tts_engine_combo.setCurrentText(CONFIG["tts_engine"])
        self.elevenlabs_key_input.setText(CONFIG["elevenlabs_key"])
        self.elevenlabs_voice_id_input.setText(CONFIG["elevenlabs_voice_id"])
        self.openai_tts_combo.setCurrentText(CONFIG["openai_tts_voice"])
        
        # Load OpenAI TTS speed setting
        speed_value = CONFIG.get("openai_tts_speed", 1.0)
        self.openai_tts_speed_slider.setValue(int(speed_value * 100))
        self.update_speed_label()  # Update the label to show current value
        
        self.aivisspeech_style_id = CONFIG.get("aivisspeech_style_id")
        self.voicevox_style_id = CONFIG.get("voicevox_style_id")

        # Load Qwen3-TTS settings
        self.qwen3_model_combo.setCurrentText(
            CONFIG.get("qwen3_tts_model", "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign")
        )
        self.qwen3_voice_prompt_input.setPlainText(
            CONFIG.get("qwen3_tts_voice_prompt", "高音萝莉女声，音调偏高且起伏明显，语气活泼可爱，带有轻微撒娇感")
        )
        self.qwen3_python_path_input.setText(CONFIG.get("qwen3_python_path", ""))

        # Load UI preference settings
        self.disable_audio_checkbox.setChecked(CONFIG.get("disable_audio", False))
        self.hide_button_checkbox.setChecked(CONFIG.get("hide_button", False))
        self.disable_text_generation_checkbox.setChecked(CONFIG.get("disable_text_generation", False))
        
        self.update_tts_panels()
        self.update_text_generation_panels()

    def save_and_close(self):
        # Update config with dialog values
        CONFIG["note_type"] = self.note_type_combo.currentText()
        CONFIG["word_field"] = self.word_field_combo.currentText()
        CONFIG["sentence_field"] = self.sentence_field_combo.currentText()
        CONFIG["explanation_field"] = self.explanation_field_combo.currentText()
        CONFIG["explanation_audio_field"] = self.explanation_audio_field_combo.currentText()

        # Save Text Generation settings
        CONFIG["openai_key"] = self.openai_key.text()
        CONFIG["openai_model"] = self.model_dropdown.currentText()
        CONFIG["gpt_prompt"] = self.gpt_prompt_input.toPlainText()

        # Save TTS settings
        CONFIG["tts_engine"] = self.tts_engine_combo.currentText()
        CONFIG["elevenlabs_key"] = self.elevenlabs_key_input.text()
        CONFIG["elevenlabs_voice_id"] = self.elevenlabs_voice_id_input.text()
        CONFIG["openai_tts_voice"] = self.openai_tts_combo.currentText()
        CONFIG["openai_tts_speed"] = self.openai_tts_speed_slider.value() / 100.0

        # Save Qwen3-TTS settings
        CONFIG["qwen3_tts_model"] = self.qwen3_model_combo.currentText()
        CONFIG["qwen3_tts_voice_prompt"] = self.qwen3_voice_prompt_input.toPlainText().strip()
        CONFIG["qwen3_python_path"] = self.qwen3_python_path_input.text().strip()

        # Save UI preference settings
        CONFIG["disable_audio"] = self.disable_audio_checkbox.isChecked()
        CONFIG["hide_button"] = self.hide_button_checkbox.isChecked()
        CONFIG["disable_text_generation"] = self.disable_text_generation_checkbox.isChecked()
        
        # Save to disk
        save_config()
        self.accept()

    def update_text_generation_panels(self):
        """Hide/show text generation settings based on disable_text_generation checkbox"""
        # If text generation is disabled, hide all text generation settings
        is_disabled = self.disable_text_generation_checkbox.isChecked()
        self.text_generation_settings_widget.setVisible(not is_disabled)

    def update_speed_label(self):
        """Update the speed label when the slider value changes"""
        speed_value = self.openai_tts_speed_slider.value() / 100.0
        self.openai_tts_speed_label.setText(f"{speed_value:.1f}x")

    def update_tts_panels(self):
        # Show the panel matching the selected TTS engine only
        engine = self.tts_engine_combo.currentText()
        
        # If audio is disabled, hide all TTS panels
        if self.disable_audio_checkbox.isChecked():
            self.panel_voicevox.setVisible(False)
            self.panel_elevenlabs.setVisible(False)
            self.panel_openai_tts.setVisible(False)
            self.panel_aivisspeech.setVisible(False)
            self.panel_qwen3_tts.setVisible(False)
            self.engine_selection_widget.setVisible(False)
        else:
            self.engine_selection_widget.setVisible(True)
            self.panel_voicevox.setVisible(engine == "VoiceVox")
            self.panel_elevenlabs.setVisible(engine == "ElevenLabs")
            self.panel_openai_tts.setVisible(engine == "OpenAI TTS")
            self.panel_aivisspeech.setVisible(engine == "AivisSpeech")
            self.panel_qwen3_tts.setVisible(engine == "Qwen3-TTS")

    def validate_elevenlabs_key(self):
        # Simple key validation for ElevenLabs
        key = self.elevenlabs_key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Missing Key", "Please enter your ElevenLabs API key.")
            return
        try:
            r = requests.get("https://api.elevenlabs.io/v2/voices", headers={"xi-api-key": key}, timeout=10)
            r.raise_for_status()
            QMessageBox.information(self, "Key Valid", "ElevenLabs API key is valid.")
        except Exception as e:
            QMessageBox.critical(self, "Validation Failed", f"Key validation failed: {e}")

    def validate_openai_key(self):
        # Simple check for OpenAI key validity
        key = self.openai_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Missing Key", "Please enter your OpenAI API key.")
            return
        try:
            h = {"Authorization": f"Bearer {key}"}
            r = requests.get("https://api.openai.com/v1/models", headers=h, timeout=10)
            r.raise_for_status()
            QMessageBox.information(self, "Key Valid", "OpenAI API key is valid.")
        except Exception as e:
            QMessageBox.critical(self, "Validation Failed", f"Key validation failed: {e}")

    def test_voicevox_connection(self):
        """Test the connection to VOICEVOX and show detailed results"""
        # Ensure latest engine selection is used
        CONFIG["tts_engine"] = self.tts_engine_combo.currentText()
        try:
            # Try to connect to VOICEVOX with more detailed diagnostics
            is_running = check_voicevox_running()
            
            if is_running:
                # Try to generate a very small test audio to confirm full functionality
                test_text = "テスト"
                test_result = backend_generate_audio("", test_text)
                
                if test_result:
                    # Success! Show confirmation message with path to audio file
                    QMessageBox.information(self, "VOICEVOX Connection Successful", 
                        f"Successfully connected to VOICEVOX and generated test audio.\n\n"
                        f"Audio file: {test_result}\n\n"
                        f"Audio generation should work correctly.")
                else:
                    # Connected but couldn't generate audio
                    QMessageBox.warning(self, "VOICEVOX Partial Connection", 
                        "Connected to VOICEVOX server, but failed to generate test audio.\n\n"
                        "Possible issues:\n"
                        "- VOICEVOX server is running but not responding to synthesis requests\n"
                        "- Permission issues with the media directory\n"
                        "- Audio generation timeout\n\n"
                        "Please check the debug logs for more details.")
            else:
                # Couldn't connect to VOICEVOX
                QMessageBox.critical(self, "VOICEVOX Connection Failed", 
                    "Failed to connect to VOICEVOX server.\n\n"
                    "Please ensure VOICEVOX is running and the API server is enabled.\n\n"
                    "Common issues:\n"
                    "- VOICEVOX application is not started\n"
                    "- API server is disabled in VOICEVOX settings\n"
                    "- VOICEVOX is using a different port (default is 50021)\n"
                    "- Firewall is blocking connections to VOICEVOX\n\n"
                )
        except Exception as e:
            debug_log(f"Error during VOICEVOX connection test: {str(e)}")
            QMessageBox.critical(self, "Test Error", 
                "An error occurred while testing VOICEVOX connection")

    def test_aivisspeech_connection(self):
        """Test the connection to AivisSpeech and show detailed results"""
        # Ensure latest engine selection is used
        CONFIG["tts_engine"] = self.tts_engine_combo.currentText()
        try:
            # Directly use the imported function
            is_running = check_aivisspeech_running(base_url="http://127.0.0.1:10101")

            if is_running:
                QMessageBox.information(self, "AivisSpeech Connection Successful", 
                    "Successfully connected to AivisSpeech engine on http://127.0.0.1:10101.")
            else:
                QMessageBox.critical(self, "AivisSpeech Connection Failed", 
                    "Failed to connect to AivisSpeech engine on http://127.0.0.1:10101.\n\n"
                    "Please ensure AivisSpeech Engine is running and accessible.")
        except Exception as e:
            debug_log(f"Error during AivisSpeech connection test: {str(e)}")
            QMessageBox.critical(self, "Test Error", 
                f"An error occurred while testing AivisSpeech connection:\n\n{str(e)}")

    def test_qwen3_tts(self):
        """Generate a short sample with the current Qwen3-TTS settings and play it."""
        voice_prompt = self.qwen3_voice_prompt_input.toPlainText().strip()
        model = self.qwen3_model_combo.currentText()

        if not voice_prompt:
            QMessageBox.warning(self, "Missing Voice Prompt",
                                "Please enter a voice style prompt before testing.")
            return

        self.qwen3_test_btn.setEnabled(False)
        self.qwen3_test_btn.setText("Generating sample…")

        sample_text = "你好！这是一个测试。"

        def run_test():
            try:
                sound_tag = backend_generate_audio(
                    api_key=None,
                    text=sample_text,
                    engine_override="Qwen3-TTS",
                    qwen3_model=model,
                    qwen3_voice_prompt=voice_prompt,
                    save_to_collection_override=True,
                )
                def on_done():
                    self.qwen3_test_btn.setEnabled(True)
                    self.qwen3_test_btn.setText("Test Qwen3-TTS (generates a sample)")
                    if sound_tag and sound_tag.startswith("[sound:") and sound_tag.endswith("]"):
                        filename = sound_tag[7:-1]
                        try:
                            from aqt.sound import play
                            play(filename)
                        except Exception as e:
                            QMessageBox.critical(self, "Playback Error",
                                                 f"Audio was generated but could not be played: {e}")
                    else:
                        QMessageBox.critical(self, "Test Failed",
                                             "Qwen3-TTS did not return a valid audio file.\n\n"
                                             "Make sure the model is downloaded and your GPU has enough VRAM.")
                mw.taskman.run_on_main(on_done)
            except Exception as e:
                debug_log(f"Qwen3-TTS test error: {e}")
                def on_error():
                    self.qwen3_test_btn.setEnabled(True)
                    self.qwen3_test_btn.setText("Test Qwen3-TTS (generates a sample)")
                    QMessageBox.critical(self, "Test Error",
                                         f"An error occurred while testing Qwen3-TTS:\n\n{e}")
                mw.taskman.run_on_main(on_error)

        import threading
        threading.Thread(target=run_test, daemon=True).start()

    def load_aivisspeech_voices_ui(self):
        debug_log("Attempting to load AivisSpeech voices for UI...")
        voices = get_aivisspeech_voices() # Assumes base_url is default http://127.0.0.1:10101
        self.aivisspeech_voices_table.setRowCount(0) # Clear existing rows

        if voices is None:
            QMessageBox.warning(self, "Load Voices Failed", "Could not retrieve voices from AivisSpeech. Is it running?")
            return
        
        if not voices:
            QMessageBox.information(self, "No Voices Found", "AivisSpeech is running, but no voices were found.")
            return

        self.aivisspeech_voices_table.setRowCount(len(voices))
        for i, voice_info in enumerate(voices):
            speaker_name = voice_info.get('speaker_name', 'N/A')
            style_name = voice_info.get('style_name', 'N/A')
            style_id = voice_info.get('style_id')

            self.aivisspeech_voices_table.setItem(i, 0, QTableWidgetItem(speaker_name))
            self.aivisspeech_voices_table.setItem(i, 1, QTableWidgetItem(style_name))

            play_btn = QPushButton("Play")
            # Store style_id in the button itself or use a lambda with default argument
            play_btn.setProperty("style_id", style_id) 
            qconnect(play_btn.clicked, lambda checked=False, sid=style_id: self.play_aivisspeech_sample_ui(sid))
            self.aivisspeech_voices_table.setCellWidget(i, 2, play_btn)
            
            default_btn = QPushButton("Set Default")
            default_btn.setProperty("style_id", style_id)
            qconnect(default_btn.clicked, lambda checked=False, sid=style_id: self.set_aivisspeech_default_style(sid))
            self.aivisspeech_voices_table.setCellWidget(i, 3, default_btn)

        # Highlight currently selected default voice if it exists
        current_default_id = CONFIG.get("aivisspeech_style_id")
        if current_default_id is not None:
            for i in range(self.aivisspeech_voices_table.rowCount()):
                button_widget = self.aivisspeech_voices_table.cellWidget(i, 3)
                if button_widget and button_widget.property("style_id") == current_default_id:
                    self.aivisspeech_voices_table.selectRow(i) # Visually indicate
                    # You might want to change button text or style too
                    break
        debug_log(f"Displayed {len(voices)} AivisSpeech voices in table.")

    def play_aivisspeech_sample_ui(self, style_id):
        if style_id is None:
            QMessageBox.warning(self, "Play Sample Error", "No style ID provided for the sample.")
            return

        sample_text = "こんにちは。日本へようこそ。"
        debug_log(f"Playing AivisSpeech sample for style_id {style_id} with text: '{sample_text}'")

        # 1) Ask the TTS routine to save into collection.media
        sound_tag = backend_generate_audio(
            api_key=None,
            text=sample_text,
            engine_override="AivisSpeech",
            style_id_override=style_id,
            save_to_collection_override=True,
        )

        # 2) We expect a string like "[sound:voice_filename.wav]"
        if sound_tag and sound_tag.startswith("[sound:") and sound_tag.endswith("]"):
            filename = sound_tag[7:-1]  # strip off "[" and "]"
            debug_log(f"Sample audio saved to collection.media as: {filename}, playing now.")
            try:
                # 3) Play via Anki's built-in sound player
                from aqt.sound import play
                play(filename)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Playback Error",
                    f"Could not play audio sample: {e}"
                )
                debug_log(f"Error playing sample from media folder: {e}")
        else:
            # fallback if generation failed
            QMessageBox.critical(
                self,
                "Sample Generation Failed",
                "Could not generate audio sample from AivisSpeech."
            )
            debug_log("Failed to generate or find audio sample file.")

    def load_voicevox_voices_ui(self):
        debug_log("Loading VoiceVox voices into UI...")
        try:
            response = requests.get("http://127.0.0.1:50021/speakers", timeout=5)
            response.raise_for_status()
            speakers = response.json()
        except Exception as e:
            QMessageBox.warning(self, "Load Voices Failed",
                                f"Could not retrieve voices from VoiceVox: {e}")
            return

        # Build list of (speaker, style, style_id)
        voices = []
        for sp in speakers:
            name = sp.get("name", "Unknown")
            for st in sp.get("styles", []):
                voices.append((name, st.get("name", "Default"), st.get("id")))

        self.voicevox_voices_table.setRowCount(len(voices))
        for row, (name, style_name, style_id) in enumerate(voices):
            self.voicevox_voices_table.setItem(row, 0, QTableWidgetItem(name))
            self.voicevox_voices_table.setItem(row, 1, QTableWidgetItem(style_name))

            # Play button
            play_btn = QPushButton("Play")
            qconnect(play_btn.clicked, lambda _, sid=style_id: self.play_voicevox_sample_ui(sid))
            self.voicevox_voices_table.setCellWidget(row, 2, play_btn)

            # Set Default button
            default_btn = QPushButton("Set Default")
            default_btn.setProperty("style_id", style_id)
            qconnect(default_btn.clicked, lambda _, sid=style_id: self.set_voicevox_default_style(sid))
            self.voicevox_voices_table.setCellWidget(row, 3, default_btn)

        # Highlight existing default style
        current = CONFIG.get("voicevox_style_id")
        if current is not None:
            for r in range(self.voicevox_voices_table.rowCount()):
                btn = self.voicevox_voices_table.cellWidget(r, 3)
                if btn and btn.property("style_id") == current:
                    self.voicevox_voices_table.selectRow(r)
                    break

    def play_voicevox_sample_ui(self, style_id):
        if style_id is None:
            QMessageBox.warning(self, "Play Sample Error", "No VoiceVox style ID provided for the sample.")
            return

        sample_text = "こんにちは。日本へようこそ。"
        debug_log(f"Playing VoiceVox sample for style_id {style_id} with text: '{sample_text}'")
        # Generate and save into collection.media
        result = backend_generate_audio(
            api_key=None,
            text=sample_text,
            engine_override="VoiceVox",
            style_id_override=style_id,
            save_to_collection_override=True
        )
        if result:
            # result may be a sound tag or a direct file path
            if result.startswith("[sound:") and result.endswith("]"):
                filename = result[7:-1]  # strip off the sound tag brackets
            else:
                filename = os.path.basename(result)

            debug_log(f"Sample audio saved as: {filename}, playing now.")
            try:
                from aqt.sound import play
                play(filename)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Playback Error",
                    f"Could not play audio sample: {e}"
                )
                debug_log(f"Error playing VoiceVox sample from media folder: {e}")
        else:
            QMessageBox.critical(
                self,
                "Sample Generation Failed",
                "Could not generate audio sample from VoiceVox."
            )
            debug_log("Failed to generate VoiceVox sample.")

    def set_aivisspeech_default_style(self, style_id):
        self.selected_aivisspeech_style_id = style_id
        CONFIG["aivisspeech_style_id"] = style_id # Also update live CONFIG
        QMessageBox.information(self, "Default Voice Set", f"AivisSpeech voice style ID {style_id} has been set as the default for new generations.")
        # Re-highlight or update UI
        self.aivisspeech_voices_table.clearSelection()
        for i in range(self.aivisspeech_voices_table.rowCount()):
            button_widget = self.aivisspeech_voices_table.cellWidget(i, 3) # Check the "Set Default" button
            if button_widget and button_widget.property("style_id") == style_id:
                self.aivisspeech_voices_table.selectRow(i)
                # Optionally, change button text to "Current Default" or disable it
                break
        debug_log(f"AivisSpeech default style ID set to: {style_id}")

    def set_voicevox_default_style(self, style_id):
        CONFIG["voicevox_style_id"] = style_id
        QMessageBox.information(self, "Default Style Set",
                                f"VoiceVox style ID {style_id} has been set as the default.")
        self.voicevox_voices_table.clearSelection()
        for i in range(self.voicevox_voices_table.rowCount()):
            btn = self.voicevox_voices_table.cellWidget(i, 3)
            if btn and btn.property("style_id") == style_id:
                self.voicevox_voices_table.selectRow(i)
                break

    def open_language_learning_community(self):
        """Open the Matt vs Japan language learning community URL in the default browser"""
        try:
            webbrowser.open("https://www.skool.com/mattvsjapan/about?ref=837f80b041cf40e9a3979cd1561a67b2")
            debug_log("Opened language learning community URL in browser")
        except Exception as e:
            debug_log(f"Error opening language learning community URL: {str(e)}")
            QMessageBox.warning(self, "Error", f"Could not open the webpage. Please visit:\nhttps://www.skool.com/mattvsjapan/about?ref=837f80b041cf40e9a3979cd1561a67b2")


__all__ = ["ConfigDialog"]