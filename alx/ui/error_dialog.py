"""Error details dialog for displaying batch processing failures."""

from __future__ import annotations

from typing import Dict, Tuple

from aqt.qt import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QApplication,
    QMessageBox,
)


class ErrorDetailsDialog(QDialog):
    """Dialog for displaying detailed error information from batch processing."""

    def __init__(
        self,
        parent=None,
        errors: Dict[int, Tuple[str, str]] = None,
        success_count: int = 0,
        skipped_count: int = 0,
        missing_fields_count: int = 0,
    ):
        """
        Initialize the error details dialog.

        Args:
            parent: Parent widget
            errors: Dict mapping note_id -> (word/card_info, error_message)
            success_count: Number of successfully processed cards
            skipped_count: Number of skipped cards
            missing_fields_count: Number of cards with missing fields
        """
        super().__init__(parent)
        self.errors = errors or {}
        self.success_count = success_count
        self.skipped_count = skipped_count
        self.missing_fields_count = missing_fields_count

        self.setWindowTitle("Batch Processing - Error Details")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Summary section
        summary_label = QLabel(self._build_summary())
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet(
            """
            QLabel {
                background-color: palette(alternatebase);
                color: palette(text);
                padding: 10px;
                border-radius: 5px;
                margin-bottom: 10px;
                border: 1px solid palette(mid);
                font-weight: bold;
            }
            """
        )
        layout.addWidget(summary_label)

        # Troubleshooting hints section
        hints = self._build_troubleshooting_hints()
        if hints:
            hints_label = QLabel(hints)
            hints_label.setWordWrap(True)
            hints_label.setStyleSheet(
                """
                QLabel {
                    background-color: #2d4a2d;
                    color: #b8e6b8;
                    padding: 10px;
                    border-radius: 5px;
                    margin-bottom: 10px;
                    border: 1px solid #4a7c4a;
                }
                """
            )
            layout.addWidget(hints_label)

        # Error details section
        error_label = QLabel("Error Details:")
        error_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        layout.addWidget(error_label)

        # Scrollable text area for errors
        self.error_text = QTextEdit()
        self.error_text.setReadOnly(True)
        self.error_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.error_text.setHtml(self._build_error_html())
        layout.addWidget(self.error_text)

        # Button layout
        button_layout = QHBoxLayout()

        copy_button = QPushButton("Copy to Clipboard")
        copy_button.clicked.connect(self._copy_to_clipboard)
        button_layout.addWidget(copy_button)

        support_button = QPushButton("Contact Support")
        support_button.clicked.connect(self._show_contact_support)
        button_layout.addWidget(support_button)

        button_layout.addStretch()

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setDefault(True)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    def _build_summary(self) -> str:
        """Build the summary text."""
        error_count = len(self.errors)
        total = self.success_count + self.skipped_count + self.missing_fields_count + error_count

        summary = f"Batch Processing Complete - {total} cards processed\n"
        summary += f"✓ {self.success_count} succeeded | "
        summary += f"⊘ {self.skipped_count} skipped | "
        summary += f"⚠ {self.missing_fields_count} missing fields | "
        summary += f"✗ {error_count} failed"

        return summary

    def _build_troubleshooting_hints(self) -> str:
        """Analyze errors and provide contextual troubleshooting hints."""
        if not self.errors:
            return ""

        hints = set()
        all_errors_text = " ".join([error_msg for _, (_, error_msg) in self.errors.items()])

        # Check for AivisSpeech errors
        if "AivisSpeech" in all_errors_text or "aivis" in all_errors_text.lower():
            hints.add("💡 AivisSpeech error detected: Is the AivisSpeech server running? (Default: http://127.0.0.1:10101)")

        # Check for VoiceVox errors
        if "VoiceVox" in all_errors_text or "VOICEVOX" in all_errors_text:
            hints.add("💡 VoiceVox error detected: Is the VoiceVox server running? (Default: http://localhost:50021)")

        # Check for ElevenLabs errors
        if "ElevenLabs" in all_errors_text or "elevenlabs" in all_errors_text.lower():
            hints.add("💡 ElevenLabs error detected: Check your ElevenLabs API key and make sure you have sufficient credits.")

        # Check for OpenAI TTS errors
        if "OpenAI TTS" in all_errors_text:
            hints.add("💡 OpenAI TTS error detected: Check your OpenAI API key and that your account supports text-to-speech.")

        # Check for internet connection issues
        if any(keyword in all_errors_text for keyword in [
            "Failed to resolve",
            "nodename nor servname provided",
            "NameResolutionError",
            "Failed to connect",
            "Connection refused",
            "No route to host",
            "Network is unreachable"
        ]):
            hints.add("💡 Connection error detected: Are you connected to the internet?")

        # Check for API authentication errors
        if any(keyword in all_errors_text for keyword in [
            "HTTP 401",
            "HTTP 403",
            "Incorrect API key",
            "Invalid API key",
            "authentication"
        ]):
            hints.add("💡 Authentication error: Check your API key in the settings. Make sure it's correct and has sufficient permissions.")

        # Check for rate limiting
        if any(keyword in all_errors_text for keyword in [
            "HTTP 429",
            "Rate limit",
            "Too many requests"
        ]):
            hints.add("💡 Rate limit reached: You've made too many requests. Wait a few minutes before trying again.")

        # Check for quota/billing/credits issues
        if any(keyword in all_errors_text for keyword in [
            "quota",
            "insufficient_quota",
            "billing",
            "exceeded your current quota",
            "insufficient credits",
            "out of credits",
            "no credits",
            "credit balance"
        ]):
            hints.add("💡 Credits/Quota issue: You may be out of credits or have exceeded your quota. Check your account balance and billing settings.")

        # Check for timeout errors
        if "timeout" in all_errors_text.lower():
            hints.add("💡 Timeout error: The request took too long. Try reducing batch size or check your internet connection speed.")

        # Check for invalid model errors
        if any(keyword in all_errors_text for keyword in [
            "model does not exist",
            "invalid model",
            "model not found"
        ]):
            hints.add("💡 Invalid model: Check that the model name in settings is correct (e.g., 'gpt-4', 'gpt-3.5-turbo').")

        if hints:
            return "<b>💭 Troubleshooting Tips:</b><br>" + "<br>".join(sorted(hints))
        return ""

    def _build_error_html(self) -> str:
        """Build HTML for the error details with highlighting."""
        if not self.errors:
            return "<p style='color: gray; font-style: italic;'>No errors to display.</p>"

        html = "<style>"
        html += "body { font-family: monospace; }"
        html += ".error-block { margin: 15px 0; padding: 10px; background-color: #2d2d2d; border-left: 4px solid #d32f2f; }"
        html += ".error-header { color: #ff6b6b; font-weight: bold; margin-bottom: 5px; }"
        html += ".card-info { color: #88ccff; margin-bottom: 5px; }"
        html += ".error-message { color: #ffcccc; white-space: pre-wrap; }"
        html += ".note-id { color: #999999; font-size: 0.9em; }"
        html += "</style>"

        html += f"<div style='padding: 10px;'>"
        html += f"<p style='color: #ff6b6b; font-weight: bold;'>Found {len(self.errors)} failed card(s):</p>"

        for i, (note_id, (card_info, error_message)) in enumerate(self.errors.items(), 1):
            html += "<div class='error-block'>"
            html += f"<div class='error-header'>Error #{i}</div>"
            html += f"<div class='card-info'>Card: {self._escape_html(card_info)}</div>"
            html += f"<div class='note-id'>Note ID: {note_id}</div>"
            html += f"<div class='error-message'>{self._escape_html(error_message)}</div>"
            html += "</div>"

        html += "</div>"
        return html

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    def _get_error_text(self) -> str:
        """Build the complete error text for copying/sharing."""
        text = self._build_summary() + "\n\n"

        # Add troubleshooting hints if available
        hints = self._build_troubleshooting_hints()
        if hints:
            # Strip HTML tags for plain text
            hints_plain = hints.replace("<b>", "").replace("</b>", "").replace("<br>", "\n")
            text += hints_plain + "\n\n"

        text += "=" * 80 + "\n"
        text += "ERROR DETAILS\n"
        text += "=" * 80 + "\n\n"

        for i, (note_id, (card_info, error_message)) in enumerate(self.errors.items(), 1):
            text += f"Error #{i}\n"
            text += f"Card: {card_info}\n"
            text += f"Note ID: {note_id}\n"
            text += f"Error: {error_message}\n"
            text += "-" * 80 + "\n"

        return text

    def _copy_to_clipboard(self) -> None:
        """Copy error details to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self._get_error_text())

    def _show_contact_support(self) -> None:
        """Show contact support dialog with email and error details."""
        error_text = self._get_error_text()

        support_dialog = QMessageBox(self)
        support_dialog.setWindowTitle("Contact Support")
        support_dialog.setIcon(QMessageBox.Icon.Information)
        support_dialog.setText("<b>Email Support</b>")
        support_dialog.setInformativeText(
            "Please email the error details attached to:<br><br>"
            "<b>r@rayamjad.com</b>"
        )
        support_dialog.setDetailedText(error_text)
        support_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        support_dialog.exec()


__all__ = ["ErrorDetailsDialog"]
