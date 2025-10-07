"""Bulk generation dialog for selecting batch-processing options."""

from __future__ import annotations

from typing import Iterable, Optional

from aqt import mw
from aqt.qt import QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from aqt.utils import qconnect

from ..config import CONFIG
from ..logging import debug_log


class BulkGenerationDialog(QDialog):
    """Dialog for selecting batch generation options."""

    def __init__(self, parent=None, selected_notes: Optional[Iterable[int]] = None):
        super().__init__(parent)
        self.setWindowTitle("AI Language Explainer - Generation Options")
        self.setMinimumWidth(500)
        self.selected_notes = list(selected_notes or [])
        self._setup_ui()

        self.generate_explanation_text = False
        self.generate_explanation_audio = False

    # UI -----------------------------------------------------------------
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        instruction_label = QLabel("Select what content to generate:")
        instruction_label.setWordWrap(True)
        instruction_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        layout.addWidget(instruction_label)

        explanation_text = QLabel(
            "When generation is checked, <b>all</b> selected cards will be overridden for that "
            "content type.<br>Deselect any cards in the browser you do not want to be changed."
        )
        explanation_text.setWordWrap(True)
        explanation_text.setStyleSheet(
            """
            QLabel {
                color: #CCCCCC;
                font-size: 13px;
                margin-bottom: 10px;
            }
            """
        )
        layout.addWidget(explanation_text)

        self.generate_text_checkbox = QCheckBox("Generate Explanation Text")
        self.generate_audio_checkbox = QCheckBox("Generate Explanation Audio")
        layout.addWidget(self.generate_text_checkbox)
        layout.addWidget(self.generate_audio_checkbox)

        qconnect(self.generate_text_checkbox.toggled, self.update_statistics)
        qconnect(self.generate_audio_checkbox.toggled, self.update_statistics)

        self.statistics_label = QLabel("")
        self.statistics_label.setWordWrap(True)
        self.statistics_label.setStyleSheet(
            """
            QLabel {
                background-color: palette(alternatebase);
                color: palette(text);
                padding: 10px;
                border-radius: 5px;
                margin-top: 10px;
                border: 1px solid palette(mid);
            }
            """
        )
        layout.addWidget(self.statistics_label)

        self.note_label = QLabel("")
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet(
            "color: palette(mid); font-style: italic; margin-top: 10px;"
        )
        layout.addWidget(self.note_label)

        self._update_checkbox_states()
        self.update_statistics()

        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        qconnect(ok_button.clicked, self.accept)
        qconnect(cancel_button.clicked, self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    # Helpers -------------------------------------------------------------
    def _update_checkbox_states(self) -> None:
        text_disabled = CONFIG.get("disable_text_generation", False)
        audio_disabled = CONFIG.get("disable_audio", False)

        stats = (
            self._analyze_selected_notes()
            if self.selected_notes
            else {"empty_text": 0, "existing_text": 0, "empty_audio": 0, "existing_audio": 0}
        )

        notes: list[str] = []

        if text_disabled:
            self.generate_text_checkbox.setEnabled(False)
            self.generate_text_checkbox.setChecked(False)
            notes.append("Text generation is disabled in settings")
        else:
            self.generate_text_checkbox.setEnabled(True)
            self.generate_text_checkbox.setChecked(True)

        if audio_disabled:
            self.generate_audio_checkbox.setEnabled(False)
            self.generate_audio_checkbox.setChecked(False)
            notes.append("Audio generation is disabled in settings")
        else:
            self.generate_audio_checkbox.setEnabled(True)
            self.generate_audio_checkbox.setChecked(True)

        self.note_label.setText("Note: " + ", ".join(notes) + "." if notes else "")

    def update_statistics(self) -> None:
        if not self.selected_notes:
            self.statistics_label.setText("No notes provided for analysis.")
            return

        stats = self._analyze_selected_notes()
        will_generate_text = self.generate_text_checkbox.isChecked() and self.generate_text_checkbox.isEnabled()
        will_generate_audio = self.generate_audio_checkbox.isChecked() and self.generate_audio_checkbox.isEnabled()

        stats_text = f"<b>Selected Notes Analysis:</b><br>"
        stats_text += f"• {len(self.selected_notes)} total cards selected<br>"
        stats_text += (
            "• {matching} cards match configured note type ({note_type})<br>".format(
                matching=stats["matching_notes"],
                note_type=CONFIG.get("note_type", "None"),
            )
        )

        if stats["matching_notes"] > 0:
            stats_text += f"• {stats['empty_text']} cards have empty explanation text<br>"
            stats_text += f"• {stats['existing_text']} cards have existing explanation text<br>"
            stats_text += f"• {stats['empty_audio']} cards have empty explanation audio<br>"
            stats_text += f"• {stats['existing_audio']} cards have existing explanation audio<br>"

            stats_text += "<br><b>With current settings:</b><br>"
            if will_generate_text:
                stats_text += "• <b>All</b> selected cards will have explanation text <b>overridden</b><br>"
            if will_generate_audio:
                stats_text += "• <b>All</b> selected cards will have explanation audio <b>overridden</b><br>"
            if not will_generate_text and not will_generate_audio:
                stats_text += "• <i>No generation will occur with current settings</i>"

        self.statistics_label.setText(stats_text)

    def _analyze_selected_notes(self) -> dict[str, int]:
        stats = {
            "matching_notes": 0,
            "empty_text": 0,
            "existing_text": 0,
            "empty_audio": 0,
            "existing_audio": 0,
        }

        target_note_type = CONFIG.get("note_type", "")
        explanation_field = CONFIG.get("explanation_field", "")
        audio_field = CONFIG.get("explanation_audio_field", "")

        for note_id in self.selected_notes:
            try:
                note = mw.col.get_note(note_id)

                if note.note_type()["name"] != target_note_type:
                    continue

                stats["matching_notes"] += 1

                if explanation_field in note:
                    if note[explanation_field].strip():
                        stats["existing_text"] += 1
                    else:
                        stats["empty_text"] += 1

                if audio_field in note:
                    if note[audio_field].strip():
                        stats["existing_audio"] += 1
                    else:
                        stats["empty_audio"] += 1
            except Exception as err:
                debug_log(f"Error analyzing note {note_id}: {err}")
                continue

        return stats

    def get_generation_options(self) -> tuple[bool, bool, bool, bool]:
        generate_text = self.generate_text_checkbox.isChecked() and self.generate_text_checkbox.isEnabled()
        generate_audio = self.generate_audio_checkbox.isChecked() and self.generate_audio_checkbox.isEnabled()

        debug_log("=== DIALOG GENERATION OPTIONS ===")
        debug_log(
            f"Generate Text checkbox: {generate_text}, Generate Audio checkbox: {generate_audio}"
        )

        override_text = generate_text
        override_audio = generate_audio

        debug_log(
            f"Override Text: {override_text}, Override Audio: {override_audio}"
        )

        return generate_text, generate_audio, override_text, override_audio


__all__ = ["BulkGenerationDialog"]
