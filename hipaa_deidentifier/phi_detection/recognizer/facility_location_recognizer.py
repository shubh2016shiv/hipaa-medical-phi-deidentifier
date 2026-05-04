"""
FacilityLocationRecognizer — promotes spaCy ORG entities that are
healthcare facilities to LOCATION.

Design rationale
----------------
spaCy's en_core_web_lg correctly labels clinical facility names such as
"St. Mary's Hospital Emergency Department" as ORG.  Presidio's default
NerModelConfiguration explicitly lists ORG in labels_to_ignore, so these
spans never reach nlp_artifacts.entities and are silently discarded as
LOCATION candidates.

This recognizer holds its own reference to the spaCy model and calls it
directly, bypassing Presidio's entity-filter layer.  It does NOT introduce
new regex patterns for facility names:

  - Span boundaries come entirely from spaCy NER (the model's decision).
  - The _HEALTHCARE_KEYWORDS set is a *domain filter on model output*,
    not a generator of new candidates.  It restricts which ORG spans
    qualify as healthcare facilities; it cannot expand what spaCy finds.
  - Healthcare facility suffixes (Hospital, Clinic, …) are stable
    domain vocabulary, not test-set-specific enumeration.
"""

from __future__ import annotations

from typing import List, Optional

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from ...utils.logger import get_logger

logger = get_logger("recognizer.facility_location")

# Domain filter applied to spaCy ORG spans.
# A span qualifies as a healthcare facility LOCATION if its lowercased
# text contains any of these substrings.
_HEALTHCARE_KEYWORDS: frozenset[str] = frozenset(
    {
        "hospital",
        "medical center",
        "health center",
        "health system",
        "healthcare",
        "clinic",
        "emergency department",
        "emergency dept",
        "behavioral health",
        "rehabilitation center",
        "rehab center",
        "nursing facility",
        "nursing home",
        "care center",
        "outpatient center",
        "surgery center",
        "cancer center",
        "heart center",
        "urgent care",
        "women's center",
        "women's health",
        "children's hospital",
        "community health",
        "family health",
    }
)


class FacilityLocationRecognizer(EntityRecognizer):
    """Promotes spaCy ORG entities that are healthcare facilities to LOCATION.

    Presidio strips ORG from nlp_artifacts before recognizers see them
    (ORG is in NerModelConfiguration.labels_to_ignore by default).  This
    recognizer holds its own spaCy model reference and calls doc.ents
    directly, so the NER model's output is used unfiltered.
    """

    def __init__(
        self,
        name: str = "FacilityLocationRecognizer",
        supported_entities: Optional[List[str]] = None,
        supported_language: str = "en",
        confidence: float = 0.75,
        **kwargs,
    ) -> None:
        super().__init__(
            supported_entities=supported_entities or ["LOCATION"],
            supported_language=supported_language,
            name=name,
            **kwargs,
        )
        self._confidence = confidence
        self._nlp = None  # loaded lazily on first call via global config cache

    def load(self) -> None:
        pass

    def _get_nlp(self):
        """Load the spaCy model on first use, reusing the global cache."""
        if self._nlp is None:
            from config.config import config as global_config

            # get_spacy_model() reads the model name from config and uses the
            # shared ModelCache, so the model is only loaded once across the pipeline.
            self._nlp = global_config.get_spacy_model()
            logger.info("FacilityLocationRecognizer attached to spaCy model")
        return self._nlp

    def analyze(
        self,
        text: str,
        entities: List[str],
        _nlp_artifacts: NlpArtifacts | None = None,
        **kwargs,
    ) -> List[RecognizerResult]:
        """Return LOCATION results for spaCy ORG spans that are healthcare facilities.

        Args:
            text: Document text passed by Presidio's AnalyzerEngine.
            entities: Requested entity types; returns [] if LOCATION not included.
            nlp_artifacts: Unused — ORG entities are stripped from artifacts by
                Presidio's NerModelConfiguration before recognizers see them.

        Returns:
            List of RecognizerResult for qualifying facility spans.
        """
        if "LOCATION" not in entities:
            return []

        nlp = self._get_nlp()
        doc = nlp(text)

        results: List[RecognizerResult] = []
        for ent in doc.ents:
            if ent.label_ != "ORG":
                continue
            lower = ent.text.lower()
            if any(kw in lower for kw in _HEALTHCARE_KEYWORDS):
                results.append(
                    RecognizerResult(
                        entity_type="LOCATION",
                        start=ent.start_char,
                        end=ent.end_char,
                        score=self._confidence,
                    )
                )
                logger.debug(
                    "Facility promoted to LOCATION: '%s' [%d:%d]",
                    ent.text,
                    ent.start_char,
                    ent.end_char,
                )

        logger.info(
            "FacilityLocationRecognizer found %d facility location(s)", len(results)
        )
        return results
