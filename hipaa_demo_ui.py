"""
HIPAA De-identification Professional Demo UI

A professional Reflex-based user interface for demonstrating HIPAA-compliant clinical data de-identification.
This module provides an interactive demonstration targeted at clinicians and AI professionals, showcasing
the complete de-identification workflow with visual highlighting of protected health information (PHI).

Key Features:
- Interactive input for clinical text data
- Real-time PHI detection and highlighting
- De-identified output generation
- HIPAA compliance indicators
- Professional healthcare-focused design

Target Audience: Clinicians and AI/ML professionals
Purpose: Educational demonstration of HIPAA Safe Harbor de-identification process

Author: HIPAA De-identification System
Version: 1.0.0
"""

"""
Hinglish Comments:

Ye professional demo UI hai jo HIPAA de-identification ka live demonstration karta hai.
Ye module clinicians aur AI professionals ke liye design kiya gaya hai, jisme:

1. Clinical text input - Raw medical data enter karne ke liye
2. PHI highlighting - HIPAA identifiers ko visually highlight karta hai
3. De-identified output - Safe, de-identified text generate karta hai
4. Professional layout - Healthcare standards ke according clean aur professional look
5. Compliance messaging - HIPAA Safe Harbor guidelines ke according warnings aur disclaimers

Ye UI enterprise-grade hai aur real-world clinical workflows ko demonstrate karta hai.
"""

import reflex as rx
from typing import Dict, List, Any, Optional
import json

# Import the HIPAA de-identifier
from hipaa_deidentifier.deidentifier import HIPAADeidentifier
from config.config import config as global_config

# Sample clinical text for demonstration
DEFAULT_SAMPLE_TEXT = """Patient Name: Johnathan M. Carter
Date of Birth: 03/12/1958
Medical Record Number (MRN): 54782934
Address: 2456 Oakwood Drive, Springfield, IL 62704
Phone: (217) 555-0187

Chief Complaint:
Patient presents for follow-up of type 2 diabetes mellitus and hypertension.

History of Present Illness:
Mr. Carter is a 67-year-old male with a history of type 2 diabetes and hypertension.
He reports adherence to metformin and lisinopril medications.
Blood glucose logs show values ranging 145–170 mg/dL.

Assessment:
1. Type 2 Diabetes Mellitus
2. Hypertension

Plan:
Continue current medications and lifestyle modifications.
Follow-up in clinic in 3 months.

Provider: Dr. Linda Thompson, MD
Mercy General Hospital
Date: 09/05/2025"""


class DeidentificationState(rx.State):
    """State management for the de-identification demo UI."""

    # Input text
    input_text: str = DEFAULT_SAMPLE_TEXT

    # Processing results
    highlighted_text: str = ""
    deidentified_text: str = ""
    detected_entities: List[Dict] = []

    # UI state
    is_processing: bool = False
    error_message: str = ""

    def update_input_text(self, text: str):
        """Update input text and trigger processing."""
        self.input_text = text
        if text.strip():
            self.process_text()

    def process_text(self):
        """Process the input text for de-identification."""
        if not self.input_text.strip():
            self.error_message = "Please enter some text to process."
            return

        try:
            self.is_processing = True
            self.error_message = ""

            # Initialize de-identifier (using cached instance for performance)
            deidentifier = HIPAADeidentifier()

            # Get de-identification results
            result = deidentifier.deidentify(self.input_text)

            # Generate highlighted text for PHI entities
            self._generate_highlighted_text(result)

            # Store results
            self.deidentified_text = result["text"]
            self.detected_entities = result["entities"]

        except Exception as e:
            self.error_message = f"Error processing text: {str(e)}"
            self.highlighted_text = ""
            self.deidentified_text = ""
            self.detected_entities = []
        finally:
            self.is_processing = False

    def _generate_highlighted_text(self, result: Dict):
        """Generate HTML with PHI highlighting for display."""
        text = self.input_text
        entities = sorted(result["entities"], key=lambda x: x["start"], reverse=True)

        # PHI category colors (professional healthcare colors)
        phi_colors = {
            "PERSON": "#FF6B6B",      # Red for patient names
            "DATE_TIME": "#4ECDC4",   # Teal for dates
            "LOCATION": "#45B7D1",    # Blue for locations
            "PHONE_NUMBER": "#FFA07A", # Orange for phones
            "ID": "#98D8C8",         # Mint for IDs
            "EMAIL": "#F7DC6F",      # Yellow for emails
            "AGE": "#BB8FCE",        # Purple for ages
            "ORGANIZATION": "#85C1E9" # Light blue for organizations
        }

        highlighted_text = text
        for entity in entities:
            start, end = entity["start"], entity["end"]
            category = entity["category"]
            confidence = entity["confidence"]

            # Get color for this PHI category
            color = phi_colors.get(category, "#95A5A6")  # Default gray

            # Create highlighted span
            original_text = highlighted_text[start:end]
            highlighted_span = f'<span style="background-color: {color}; padding: 2px 4px; border-radius: 3px; font-weight: bold;" title="PHI: {category} (confidence: {confidence:.2f})">{original_text}</span>'

            # Replace in the text
            highlighted_text = highlighted_text[:start] + highlighted_span + highlighted_text[end:]

        self.highlighted_text = highlighted_text

    def get_phi_summary(self) -> str:
        """Generate summary of detected PHI entities."""
        if not self.detected_entities:
            return "No PHI detected in the input text."

        summary = f"Detected {len(self.detected_entities)} PHI entities:\n\n"
        category_counts = {}

        for entity in self.detected_entities:
            category = entity["category"]
            category_counts[category] = category_counts.get(category, 0) + 1

        for category, count in sorted(category_counts.items()):
            summary += f"• {category}: {count} instances\n"

        return summary

    def clear_all(self):
        """Clear all input and results."""
        self.input_text = ""
        self.highlighted_text = ""
        self.deidentified_text = ""
        self.detected_entities = []
        self.error_message = ""


def phi_legend():
    """Display legend for PHI highlighting colors."""
    return rx.box(
        rx.heading("PHI Detection Legend", size="sm", margin_bottom="0.5em"),
        rx.grid(
            rx.hstack(
                rx.box(width="16px", height="16px", background="#FF6B6B", border_radius="2px"),
                rx.text("Patient Names", font_size="sm"),
                spacing="0.5em",
                align_items="center"
            ),
            rx.hstack(
                rx.box(width="16px", height="16px", background="#4ECDC4", border_radius="2px"),
                rx.text("Dates", font_size="sm"),
                spacing="0.5em",
                align_items="center"
            ),
            rx.hstack(
                rx.box(width="16px", height="16px", background="#45B7D1", border_radius="2px"),
                rx.text("Locations", font_size="sm"),
                spacing="0.5em",
                align_items="center"
            ),
            rx.hstack(
                rx.box(width="16px", height="16px", background="#FFA07A", border_radius="2px"),
                rx.text("Phone Numbers", font_size="sm"),
                spacing="0.5em",
                align_items="center"
            ),
            columns="2",
            spacing="0.5em"
        ),
        rx.grid(
            rx.hstack(
                rx.box(width="16px", height="16px", background="#98D8C8", border_radius="2px"),
                rx.text("Medical IDs", font_size="sm"),
                spacing="0.5em",
                align_items="center"
            ),
            rx.hstack(
                rx.box(width="16px", height="16px", background="#F7DC6F", border_radius="2px"),
                rx.text("Email Addresses", font_size="sm"),
                spacing="0.5em",
                align_items="center"
            ),
            rx.hstack(
                rx.box(width="16px", height="16px", background="#BB8FCE", border_radius="2px"),
                rx.text("Ages", font_size="sm"),
                spacing="0.5em",
                align_items="center"
            ),
            rx.hstack(
                rx.box(width="16px", height="16px", background="#85C1E9", border_radius="2px"),
                rx.text("Organizations", font_size="sm"),
                spacing="0.5em",
                align_items="center"
            ),
            columns="2",
            spacing="0.5em"
        ),
        padding="1em",
        border="1px solid #E2E8F0",
        border_radius="8px",
        background="#F8FAFC",
        width="100%"
    )


def input_section():
    """Input section with text area and controls."""
    return rx.box(
        rx.vstack(
            rx.heading("Clinical Text Input", size="md", color="#1A202C"),
            rx.text(
                "Enter or paste clinical notes, patient records, or any healthcare-related text below. "
                "The system will automatically detect and highlight protected health information (PHI).",
                font_size="sm",
                color="#4A5568",
                margin_bottom="1em"
            ),
            rx.text_area(
                value=DeidentificationState.input_text,
                on_change=DeidentificationState.update_input_text,
                placeholder="Enter clinical text here...",
                height="200px",
                width="100%",
                border="2px solid #E2E8F0",
                border_radius="8px",
                padding="1em",
                font_family="monospace",
                font_size="sm",
                _focus={"border_color": "#4299E1", "box_shadow": "0 0 0 1px #4299E1"}
            ),
            rx.hstack(
                rx.button(
                    "Load Sample Text",
                    on_click=lambda: DeidentificationState.update_input_text(DEFAULT_SAMPLE_TEXT),
                    background="#4299E1",
                    color="white",
                    padding="0.5em 1em",
                    border_radius="6px",
                    _hover={"background": "#3182CE"}
                ),
                rx.button(
                    "Clear All",
                    on_click=DeidentificationState.clear_all,
                    background="#E53E3E",
                    color="white",
                    padding="0.5em 1em",
                    border_radius="6px",
                    _hover={"background": "#C53030"}
                ),
                spacing="1em"
            ),
            spacing="1em",
            width="100%"
        ),
        padding="1.5em",
        border="1px solid #E2E8F0",
        border_radius="12px",
        background="white",
        box_shadow="0 4px 6px -1px rgba(0, 0, 0, 0.1)",
        width="100%"
    )


def results_section():
    """Results section with highlighted and de-identified text."""
    return rx.box(
        rx.vstack(
            rx.heading("Processing Results", size="md", color="#1A202C"),
            rx.cond(
                DeidentificationState.is_processing,
                rx.hstack(
                    rx.spinner(size="sm", color="#4299E1"),
                    rx.text("Processing text...", color="#4A5568"),
                    spacing="0.5em"
                ),
                rx.cond(
                    DeidentificationState.error_message,
                    rx.alert(
                        rx.alert_icon(),
                        rx.alert_title("Processing Error"),
                        rx.alert_description(DeidentificationState.error_message),
                        status="error"
                    ),
                    rx.vstack(
                        phi_legend(),
                        rx.grid(
                            # Highlighted text section
                            rx.box(
                                rx.vstack(
                                    rx.heading("Original Text with PHI Highlighting", size="sm", color="#1A202C"),
                                    rx.text(
                                        "Protected Health Information (PHI) is highlighted below according to HIPAA categories:",
                                        font_size="xs",
                                        color="#4A5568",
                                        margin_bottom="0.5em"
                                    ),
                                    rx.html(
                                        DeidentificationState.highlighted_text,
                                        height="300px",
                                        padding="1em",
                                        border="1px solid #E2E8F0",
                                        border_radius="6px",
                                        background="#FAFBFC",
                                        overflow="auto",
                                        font_family="monospace",
                                        font_size="sm"
                                    ),
                                    spacing="0.5em",
                                    width="100%"
                                ),
                                padding="1em",
                                border="1px solid #E2E8F0",
                                border_radius="8px",
                                background="white"
                            ),

                            # De-identified text section
                            rx.box(
                                rx.vstack(
                                    rx.heading("De-identified Safe Text", size="sm", color="#1A202C"),
                                    rx.text(
                                        "This is the HIPAA-compliant de-identified version ready for research or sharing:",
                                        font_size="xs",
                                        color="#4A5568",
                                        margin_bottom="0.5em"
                                    ),
                                    rx.text_area(
                                        value=DeidentificationState.deidentified_text,
                                        read_only=True,
                                        height="300px",
                                        width="100%",
                                        padding="1em",
                                        border="1px solid #38A169",
                                        border_radius="6px",
                                        background="#F0FFF4",
                                        font_family="monospace",
                                        font_size="sm",
                                        overflow="auto"
                                    ),
                                    spacing="0.5em",
                                    width="100%"
                                ),
                                padding="1em",
                                border="1px solid #38A169",
                                border_radius="8px",
                                background="white"
                            ),

                            columns="2",
                            spacing="1em",
                            width="100%"
                        ),

                        # PHI Summary
                        rx.cond(
                            DeidentificationState.detected_entities.length() > 0,
                            rx.box(
                                rx.vstack(
                                    rx.heading("PHI Detection Summary", size="sm", color="#1A202C"),
                                    rx.text_area(
                                        value=DeidentificationState.get_phi_summary,
                                        read_only=True,
                                        height="120px",
                                        width="100%",
                                        padding="1em",
                                        border="1px solid #E2E8F0",
                                        border_radius="6px",
                                        background="#F8FAFC",
                                        font_family="monospace",
                                        font_size="sm"
                                    ),
                                    spacing="0.5em",
                                    width="100%"
                                ),
                                padding="1em",
                                border="1px solid #E2E8F0",
                                border_radius="8px",
                                background="white",
                                width="100%"
                            )
                        ),

                        spacing="1em",
                        width="100%"
                    )
                )
            ),
            spacing="1em",
            width="100%"
        ),
        padding="1.5em",
        border="1px solid #E2E8F0",
        border_radius="12px",
        background="white",
        box_shadow="0 4px 6px -1px rgba(0, 0, 0, 0.1)",
        width="100%"
    )


def hipaa_compliance_banner():
    """HIPAA compliance and disclaimer banner."""
    return rx.box(
        rx.vstack(
            rx.heading("⚕️ HIPAA Safe Harbor De-identification Demo", size="lg", color="#1A202C"),
            rx.text(
                "This demonstration showcases HIPAA-compliant de-identification of clinical data using advanced AI/ML techniques. "
                "All processing follows HIPAA Safe Harbor guidelines for removing 18 categories of protected health information.",
                font_size="sm",
                color="#4A5568",
                text_align="center"
            ),
            rx.alert(
                rx.alert_icon(),
                rx.alert_title("Important Disclaimer"),
                rx.alert_description(
                    "This is a demonstration tool only. De-identified data should be reviewed by qualified healthcare professionals "
                    "before use in research or other applications. Always consult with legal and compliance experts for production use."
                ),
                status="warning",
                margin_top="1em"
            ),
            spacing="1em",
            align_items="center"
        ),
        padding="2em",
        background="#EBF8FF",
        border="1px solid #BEE3F8",
        border_radius="12px",
        margin_bottom="2em",
        width="100%"
    )


def main_layout():
    """Main application layout."""
    return rx.container(
        rx.vstack(
            hipaa_compliance_banner(),
            input_section(),
            results_section(),
            spacing="2em",
            align_items="center",
            width="100%"
        ),
        max_width="1200px",
        padding="2em",
        background="#F7FAFC",
        min_height="100vh"
    )


# Create the Reflex app
app = rx.App(
    state=DeidentificationState,
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
    ],
    style={
        "font_family": "Inter, sans-serif",
        "background": "#F7FAFC"
    }
)

# Add the main page
app.add_page(main_layout, title="HIPAA De-identification Demo", route="/")

if __name__ == "__main__":
    app.run()  # This will start the Reflex development server
