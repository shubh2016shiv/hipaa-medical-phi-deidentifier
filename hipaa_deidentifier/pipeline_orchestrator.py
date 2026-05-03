"""
HIPAA De-identification Pipeline Orchestrator

Enterprise-grade orchestrator that coordinates the complete PHI detection and redaction pipeline.
Implements a multi-stage processing workflow with proper separation of concerns.

Pipeline Stages:
1. Text Normalization: Clean and standardize input text
2. PHI Detection: Multi-strategy detection (rules + ML + patterns)
3. Clinical Preservation: Identify and protect clinical terms
4. Overlap Resolution: Handle conflicting detections
5. PHI Redaction: Apply transformation strategies
6. Audit Generation: Create detailed audit trail

Enterprise Features:
- Comprehensive logging with configurable levels
- Type-safe interfaces with complete type hints
- Separation of concerns across detection strategies
- Configurable detection and redaction strategies
- Performance optimization with caching
- Professional error handling

Author: HIPAA De-identification System
Version: 2.0.0 (Enterprise Refactoring)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from config.config import config as global_config

from .models.phi_entity import PHIEntity
from .phi_detection.clinical_patterns import (
    detect_ages_over_89,
    detect_long_numeric_ids,
    detect_section_headers,
)
from .phi_detection.identifier import HFIdentifier, PresidioIdentifier
from .phi_detection.normalizer import TextNormalizer
from .phi_detection.post_detection_fp_guardrail.fp_guardrail import (
    FalsePositiveGuardrail,
)
from .phi_redaction.phi_redactor import PHIRedactor
from .utils.color_output import colorize_deidentified_text
from .utils.logger import get_logger

# Initialize module logger
logger = get_logger("orchestrator")


@dataclass
class PipelineConfiguration:
    """
    Configuration for the de-identification pipeline.

    Attributes:
        enable_rules: Enable rule-based detection (Presidio)
        enable_ml: Enable machine learning detection
        enable_header_patterns: Enable clinical header pattern detection
        enable_clinical_preservation: Enable clinical term preservation
        pattern_threshold: Minimum confidence for pattern detection
        ml_threshold: Minimum confidence for ML detection
        device: Device for ML inference (-1 for CPU, 0+ for GPU)
    """

    enable_rules: bool = True
    enable_ml: bool = True
    enable_header_patterns: bool = True
    enable_clinical_preservation: bool = True
    pattern_threshold: float = 0.5
    ml_threshold: float = (
        0.9  # HF guardrail threshold; calibrated from eval (all TPs >= 0.92)
    )
    device: int = -1


@dataclass
class DeidentificationResult:
    """
    Result of the de-identification process.

    Attributes:
        original_text: The original input text
        deidentified_text: The de-identified output text
        entities: List of detected and redacted entities
        audit_trail: Detailed audit information
        statistics: Processing statistics
    """

    original_text: str
    deidentified_text: str
    entities: List[Dict]
    audit_trail: Dict
    statistics: Dict


class HIPAAPipelineOrchestrator:
    """
    Enterprise-grade orchestrator for HIPAA de-identification pipeline.

    Coordinates the complete workflow from raw text to de-identified output,
    utilizing all refactored components with proper separation of concerns.

    Components:
    - TextNormalizer: Stage 0 text preprocessing
    - PresidioIdentifier: Rule-based PHI detection
    - HFIdentifier: ML-based PHI detection (optional)
    - Clinical pattern detectors: Header, age, numeric ID detection
    - PHIRedactor: Transformation and redaction strategies

    Features:
    - Multi-stage detection pipeline
    - Clinical term preservation
    - Overlap resolution
    - Comprehensive audit trail
    - Performance metrics
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        spacy_model: str = "en_core_web_lg",
        hf_model: str = "obi/deid_bert_i2b2",
        device: int = -1,
        pipeline_config: Optional[PipelineConfiguration] = None,
    ):
        """
        Initialize the pipeline orchestrator.

        Args:
            config_path: Path to configuration file (uses defaults if None)
            spacy_model: spaCy model for NLP processing
            hf_model: Hugging Face model for ML-based detection
            device: Device for ML inference (-1 for CPU, 0+ for GPU)
            pipeline_config: Optional pipeline configuration override

        Example:
            >>> orchestrator = HIPAAPipelineOrchestrator()
            >>> result = orchestrator.deidentify("Patient John Doe, MRN: 12345678")
        """
        logger.info("Initializing HIPAA Pipeline Orchestrator")

        # Load configuration
        if config_path is not None:
            global_config.initialize(config_path=config_path)
        self.config = global_config.get_settings()
        logger.debug(f"Configuration loaded: {len(self.config)} top-level keys")

        # Set pipeline configuration
        self.pipeline_config = pipeline_config or self._create_default_pipeline_config()
        logger.info(
            f"Pipeline configuration: rules={self.pipeline_config.enable_rules}, "
            f"ml={self.pipeline_config.enable_ml}, "
            f"headers={self.pipeline_config.enable_header_patterns}"
        )

        # Initialize Stage 0: Text Normalization
        self.text_normalizer = TextNormalizer()
        logger.info("Text normalizer initialized")

        # Initialize Stage 1: Rule-based Detection
        self.rule_based_identifier: Optional[PresidioIdentifier] = None
        if self.pipeline_config.enable_rules:
            self.rule_based_identifier = PresidioIdentifier(config=self.config)
            logger.info("Rule-based identifier (Presidio) initialized")

        # Initialize Stage 2: ML-based Detection
        self.ml_based_identifier: Optional[HFIdentifier] = None
        if self.pipeline_config.enable_ml:
            try:
                self.ml_based_identifier = HFIdentifier(
                    hf_model=hf_model, device=device, config=self.config
                )
                logger.info(
                    f"ML-based identifier initialized: {hf_model} on device {device}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to initialize ML identifier: {e}. Continuing without ML detection."
                )
                self.pipeline_config.enable_ml = False

        # Initialize Stage 3: Redaction
        self.redactor = PHIRedactor(self.config)
        logger.info("PHI redactor initialized")

        # Initialize False Positive Guardrail — threshold sourced from ml_threshold config
        self.fp_guardrail = FalsePositiveGuardrail(
            hf_threshold=self.pipeline_config.ml_threshold
        )
        logger.info("False Positive Guardrail initialized")

        # Performance tracking
        self._stats = {
            "total_processed": 0,
            "total_entities_detected": 0,
            "total_entities_redacted": 0,
        }

        logger.info("HIPAA Pipeline Orchestrator initialization complete")

    def _create_default_pipeline_config(self) -> PipelineConfiguration:
        """
        Create default pipeline configuration from main config.

        Returns:
            PipelineConfiguration with values from main config
        """
        detect_config = self.config.get("detect", {})
        thresholds = self.config.get("detection_thresholds", {})

        return PipelineConfiguration(
            enable_rules=detect_config.get("enable_rules", True),
            enable_ml=detect_config.get("enable_ml", True),
            enable_header_patterns=detect_config.get("enable_header_patterns", True),
            enable_clinical_preservation=detect_config.get(
                "enable_clinical_preservation", True
            ),
            pattern_threshold=thresholds.get("patterns", 0.5),
            ml_threshold=thresholds.get("ml", 0.7),
            device=-1,
        )

    def deidentify(
        self,
        text: str,
        patient_id: Optional[str] = None,
        include_statistics: bool = False,
    ) -> Dict:
        """
        De-identify PHI in the given text using the complete pipeline.

        Pipeline Stages:
        1. Text normalization with character mapping
        2. Multi-strategy PHI detection
        3. Clinical term preservation
        4. Overlap resolution
        5. PHI redaction
        6. Audit trail generation

        Args:
            text: The text to de-identify
            patient_id: Optional patient identifier for consistent pseudonyms
            include_statistics: Include processing statistics in result

        Returns:
            Dictionary containing:
                - text: De-identified text
                - entities: List of detected/redacted entities
                - statistics: Processing stats (if include_statistics=True)

        Example:
            >>> result = orchestrator.deidentify(
            ...     "Patient: John Doe, DOB: 01/15/1980, SSN: 123-45-6789",
            ...     patient_id="P001"
            ... )
            >>> print(result["text"])
            Patient: [REDACTED:NAME], DOB: [REDACTED:DATE], SSN: [REDACTED:US_SSN]
        """
        logger.info(
            f"Starting de-identification process (text length: {len(text)} characters)"
        )

        # Track processing time
        import time

        start_time = time.time()

        # Stage 1: Detect PHI entities
        entities = self._detect_phi_entities(text)
        logger.info(f"Detection complete: {len(entities)} entities found")

        # Stage 1.5: Apply False Positive Guardrail
        entities = self.fp_guardrail.filter(entities, text)
        logger.info(f"Guardrail complete: {len(entities)} entities retained")

        # Stage 2: Redact detected PHI
        deidentified_text = self.redactor.redact_text(text, entities, patient_id)
        logger.info("Redaction complete")

        # Stage 3: Create audit trail
        audit_trail = self._create_audit_trail(entities)

        # Update statistics
        self._stats["total_processed"] += 1
        self._stats["total_entities_detected"] += len(entities)
        self._stats["total_entities_redacted"] += len(audit_trail)

        # Calculate processing time
        processing_time = time.time() - start_time

        # Build result
        result = {"text": deidentified_text, "entities": audit_trail}

        if include_statistics:
            result["statistics"] = {
                "processing_time_seconds": round(processing_time, 3),
                "original_length": len(text),
                "deidentified_length": len(deidentified_text),
                "entities_detected": len(entities),
                "entities_redacted": len(audit_trail),
            }

        logger.info(f"De-identification complete in {processing_time:.3f}s")
        return result

    def deidentify_with_colors(
        self, text: str, patient_id: Optional[str] = None
    ) -> Dict:
        """
        De-identify text and return results with colored visualization.

        Useful for demonstrations and debugging. Adds a colorized version
        of the de-identified text highlighting different PHI categories.

        Args:
            text: The text to de-identify
            patient_id: Optional patient identifier for consistent pseudonyms

        Returns:
            Dictionary containing:
                - text: De-identified text
                - entities: List of detected/redacted entities
                - colorized_text: Color-coded visualization

        Example:
            >>> result = orchestrator.deidentify_with_colors("SSN: 123-45-6789")
            >>> print(result["colorized_text"])  # Shows colored output
        """
        logger.info("Starting de-identification with color visualization")

        # Get standard de-identification results
        result = self.deidentify(text, patient_id, include_statistics=False)

        # Add colorized text for visualization
        try:
            result["colorized_text"] = colorize_deidentified_text(
                result["text"], result["entities"]
            )
            logger.debug("Color visualization generated")
        except Exception as e:
            logger.warning(f"Failed to generate color visualization: {e}")
            result["colorized_text"] = result["text"]

        return result

    def deidentify_batch(
        self,
        texts: List[str],
        patient_ids: Optional[List[str]] = None,
        include_statistics: bool = False,
    ) -> List[Dict]:
        """
        De-identify multiple texts in batch.

        Processes multiple texts efficiently with shared model initialization.
        Useful for processing collections of clinical notes.

        Args:
            texts: List of texts to de-identify
            patient_ids: Optional list of patient IDs (must match texts length)
            include_statistics: Include processing statistics in results

        Returns:
            List of de-identification results, one per input text

        Example:
            >>> texts = ["Note 1: SSN 123-45-6789", "Note 2: MRN 987654"]
            >>> results = orchestrator.deidentify_batch(texts)
            >>> print(len(results))
            2
        """
        logger.info(f"Starting batch de-identification ({len(texts)} documents)")

        # Validate patient_ids length if provided
        if patient_ids is not None and len(patient_ids) != len(texts):
            raise ValueError(
                f"patient_ids length ({len(patient_ids)}) must match texts length ({len(texts)})"
            )

        results = []
        for idx, text in enumerate(texts):
            patient_id = patient_ids[idx] if patient_ids else None
            logger.debug(f"Processing document {idx + 1}/{len(texts)}")

            result = self.deidentify(text, patient_id, include_statistics)
            results.append(result)

        logger.info(
            f"Batch de-identification complete: {len(results)} documents processed"
        )
        return results

    def _detect_phi_entities(self, text: str) -> List[PHIEntity]:
        """
        Detect PHI entities using multi-stage pipeline.

        Stages:
        1. Text normalization with character mapping
        2. Rule-based detection (Presidio)
        3. ML-based detection (Hugging Face)
        4. Clinical header pattern detection
        5. Age over 89 detection
        6. Long numeric ID detection
        7. Span projection to original text
        8. Clinical term preservation
        9. Overlap resolution

        Args:
            text: The text to analyze

        Returns:
            List of detected PHI entities with positions in original text
        """
        logger.debug("Starting PHI detection pipeline")

        # Stage 1: Normalize text while maintaining character mapping
        normalized_result = self.text_normalizer.stage0_normalize_and_candidates(text)
        normalized_text = normalized_result["normalized_text"]
        project_fn = normalized_result["project_fn"]
        logger.debug(
            f"Text normalized: {len(text)} -> {len(normalized_text)} characters"
        )

        # Stage 2: Run all detectors on normalized text
        normalized_entities: List[PHIEntity] = []

        # Rule-based detection (Presidio)
        if self.rule_based_identifier:
            try:
                # Standard detection
                rule_entities = self.rule_based_identifier.detect(normalized_text)
                normalized_entities.extend(rule_entities)
                logger.debug(f"Rule-based detection: {len(rule_entities)} entities")

                # Header pattern detection
                header_entities = (
                    self.rule_based_identifier.detect_with_header_patterns(
                        normalized_text
                    )
                )
                normalized_entities.extend(header_entities)
                logger.debug(
                    f"Header pattern detection: {len(header_entities)} entities"
                )
            except Exception as e:
                logger.error(f"Rule-based detection failed: {e}")

        # ML-based detection (Hugging Face) on masked text
        # Mask entities already found by Presidio to prevent re-detection and reduce false positives
        if self.ml_based_identifier:
            try:
                # Create masked version of normalized text
                masked_text = list(normalized_text)
                for entity in normalized_entities:
                    for i in range(entity.start, min(entity.end, len(masked_text))):
                        masked_text[i] = "#"
                masked_text_str = "".join(masked_text)

                # Run HF on masked text
                ml_entities = self.ml_based_identifier.detect(masked_text_str)
                normalized_entities.extend(ml_entities)
                logger.debug(
                    f"ML-based detection: {len(ml_entities)} entities (on masked text)"
                )
            except Exception as e:
                logger.error(f"ML-based detection failed: {e}")

        # Clinical header pattern detection
        if self.pipeline_config.enable_header_patterns:
            try:
                header_entities = detect_section_headers(normalized_text)
                normalized_entities.extend(header_entities)
                logger.debug(
                    f"Header pattern detection: {len(header_entities)} entities"
                )
            except Exception as e:
                logger.error(f"Header pattern detection failed: {e}")

        # Age over 89 detection
        try:
            age_entities = detect_ages_over_89(normalized_text)
            normalized_entities.extend(age_entities)
            logger.debug(f"Age over 89 detection: {len(age_entities)} entities")
        except Exception as e:
            logger.error(f"Age detection failed: {e}")

        # Stage 6: Long numeric ID detection (with context)
        try:
            numeric_entities = detect_long_numeric_ids(
                normalized_text, existing_entities=normalized_entities
            )
            normalized_entities.extend(numeric_entities)
            logger.debug(f"Numeric ID detection: {len(numeric_entities)} entities")
        except Exception as e:
            logger.error(f"Numeric ID detection failed: {e}")

        # Stage 7: Project all spans back to original text
        original_entities = []
        for entity in normalized_entities:
            # Project span from normalized text back to original text
            original_span = project_fn(entity.start, entity.end)

            # Create new entity with original text positions
            original_entity = PHIEntity(
                start=original_span[0],
                end=original_span[1],
                category=entity.category,
                confidence=entity.confidence,
                text=text[
                    original_span[0] : original_span[1]
                ],  # Extract text from original
            )
            original_entity.source = getattr(
                entity, "source", "unknown"
            )  # Preserve the source
            original_entities.append(original_entity)
        logger.debug(f"Projected {len(normalized_entities)} entities to original text")

        # Stage 8: Clinical term preservation (if enabled)
        if self.pipeline_config.enable_clinical_preservation:
            original_entities = self._preserve_clinical_terms(original_entities, text)
            logger.debug(
                f"Clinical preservation: {len(original_entities)} entities after filtering"
            )

        # Stage 9: Merge related entities
        merged_entities = self._merge_related_entities(original_entities, text)
        logger.debug(
            f"Merged {len(original_entities) - len(merged_entities)} related entities"
        )

        # Stage 10: Resolve overlaps
        final_entities = self._resolve_overlaps_with_confidence(merged_entities)
        logger.debug(f"Overlap resolution: {len(final_entities)} final entities")

        return final_entities

    def _merge_related_entities(
        self, entities: List[PHIEntity], text: str
    ) -> List[PHIEntity]:
        """
        Merge related entities like date components, MRN parts, and names.
        """
        if not entities:
            return []

        sorted_entities = sorted(entities, key=lambda e: e.start)

        merged = []
        i = 0
        while i < len(sorted_entities):
            current = sorted_entities[i]

            # Look ahead for mergeable entities
            j = i + 1
            if j < len(sorted_entities):
                next_entity = sorted_entities[j]

                # Merge adjacent NAME entities
                if current.category == "NAME" and next_entity.category == "NAME":
                    between_text = text[current.end : next_entity.start]
                    if len(between_text) <= 2 and between_text.strip() in [
                        "",
                        ",",
                        " ",
                    ]:
                        merged_entity = PHIEntity(
                            start=current.start,
                            end=next_entity.end,
                            category="NAME",
                            confidence=max(current.confidence, next_entity.confidence),
                            text=text[current.start : next_entity.end],
                            source=current.source,
                        )
                        merged.append(merged_entity)
                        i += 2
                        continue

            merged.append(current)
            i += 1

        return merged

    def _resolve_overlaps_with_confidence(
        self, entities: List[PHIEntity]
    ) -> List[PHIEntity]:
        """
        Resolve overlapping entities using confidence-based voting.

        When entities overlap, choose the one with the highest confidence,
        with preference given to specialized detectors for their target identifiers.

        Args:
            entities: List of detected PHI entities

        Returns:
            List of non-overlapping PHI entities
        """
        if not entities:
            return []

        # Sort entities by start position, then by end position (longer spans first)
        sorted_entities = sorted(entities, key=lambda e: (e.start, -e.end))

        # Detector weights for voting
        detector_weights = {
            # Presidio is best for structured data
            "presidio": {
                "PHONE_NUMBER": 1.2,
                "FAX_NUMBER": 1.2,
                "EMAIL_ADDRESS": 1.2,
                "US_SSN": 1.2,
                "URL": 1.2,
                "IP_ADDRESS": 1.2,
                "LICENSE_NUMBER": 1.2,
                "VEHICLE_ID": 1.2,
                "DEVICE_ID": 1.2,
                "DEFAULT": 0.8,
            },
            "presidio_header": {
                "MRN": 1.3,
                "US_SSN": 1.3,
                "DATE": 1.3,
                "NAME": 1.3,
                "PHONE_NUMBER": 1.3,
                "FAX_NUMBER": 1.3,
                "EMAIL_ADDRESS": 1.3,
                "DEFAULT": 0.9,
            },
            # spaCy is best for general entities
            "spacy": {
                "NAME": 1.2,
                "LOCATION": 1.2,
                "ORGANIZATION": 1.2,
                "DATE": 1.2,
                "DEFAULT": 0.8,
            },
            # HF is best for medical-specific entities
            "hf": {
                "MRN": 1.2,
                "HEALTH_PLAN_ID": 1.2,
                "ACCOUNT_NUMBER": 1.2,
                "BIOMETRIC_ID": 1.2,
                "PHOTO_ID": 1.2,
                "AGE_OVER_89": 1.2,
                "DEFAULT": 0.8,
            },
            # Default for unknown sources
            "unknown": {"DEFAULT": 1.0},
        }

        # Function to calculate weighted confidence
        def weighted_confidence(entity: PHIEntity) -> float:
            source = getattr(entity, "source", "unknown")
            source_weights = detector_weights.get(source, detector_weights["unknown"])
            weight = source_weights.get(
                entity.category, source_weights.get("DEFAULT", 1.0)
            )
            return entity.confidence * weight

        # Resolve overlaps using nested loop approach (like reference project)
        final_entities = []
        for entity in sorted_entities:
            # Check if this entity overlaps with any in the final list
            overlaps = False
            for final_entity in final_entities:
                if entity.start < final_entity.end and entity.end > final_entity.start:
                    overlaps = True
                    same_category = entity.category == final_entity.category
                    entity_contains_final = (
                        entity.start <= final_entity.start
                        and entity.end >= final_entity.end
                    )
                    final_contains_entity = (
                        final_entity.start <= entity.start
                        and final_entity.end >= entity.end
                    )

                    # For the same PHI category, prefer the covering span over
                    # a smaller fragment. This prevents dates/names from being
                    # partially redacted when multiple detectors disagree on
                    # boundaries.
                    if (
                        same_category
                        and entity_contains_final
                        and not final_contains_entity
                    ):
                        final_entities.remove(final_entity)
                        final_entities.append(entity)
                    elif same_category and final_contains_entity:
                        pass
                    # If this entity has higher weighted confidence, replace the final entity
                    elif weighted_confidence(entity) > weighted_confidence(
                        final_entity
                    ):
                        final_entities.remove(final_entity)
                        final_entities.append(entity)
                    break

            # If no overlap, add to final list
            if not overlaps:
                final_entities.append(entity)

        # Sort final entities by position
        return sorted(final_entities, key=lambda e: e.start)

    def _project_entities_to_original(
        self,
        normalized_entities: List[PHIEntity],
        char_map: List[int],
        original_text: str,
    ) -> List[PHIEntity]:
        """
        Project entity positions from normalized text back to original text.

        Uses the character mapping from normalization to accurately
        map detected entity positions back to the original text.

        Args:
            normalized_entities: Entities detected in normalized text
            char_map: Character mapping from normalized to original positions
            original_text: The original input text

        Returns:
            Entities with positions in original text
        """
        original_entities = []

        for entity in normalized_entities:
            try:
                # Map positions using character map
                original_start = (
                    char_map[entity.start]
                    if entity.start < len(char_map)
                    else entity.start
                )
                original_end = (
                    char_map[entity.end - 1] + 1
                    if entity.end - 1 < len(char_map)
                    else entity.end
                )

                # Ensure valid range
                original_start = max(0, min(original_start, len(original_text)))
                original_end = max(
                    original_start, min(original_end, len(original_text))
                )

                # Extract text from original
                entity_text = original_text[original_start:original_end]

                # Create new entity with original positions
                original_entity = PHIEntity(
                    start=original_start,
                    end=original_end,
                    category=entity.category,
                    confidence=entity.confidence,
                    text=entity_text,
                )
                original_entities.append(original_entity)
            except (IndexError, ValueError) as e:
                logger.warning(
                    f"Failed to project entity {entity.category} at {entity.start}-{entity.end}: {e}"
                )
                continue

        return original_entities

    def _preserve_clinical_terms(
        self, entities: List[PHIEntity], text: str
    ) -> List[PHIEntity]:
        """
        Filter out entities that overlap with clinical terms.

        Clinical terms (vitals, labs, medications, diagnoses) should
        not be redacted as they are essential medical information.

        Args:
            entities: Detected PHI entities
            text: Original text

        Returns:
            Filtered entities with clinical terms preserved
        """
        if not entities:
            return entities

        # Clinical terms that should NOT be redacted
        clinical_patterns = [
            # Medical conditions and diseases
            r"\b(?:cancer|adenocarcinoma|carcinoma|tumor|neoplasm|metastasis|metastatic)\b",
            r"\b(?:diabetes|hypertension|pneumonia|sepsis|infection|disease|syndrome)\b",
            r"\b(?:stroke|heart attack|myocardial infarction|MI|CABG|angina)\b",
            # Medications and treatments
            r"\b(?:aspirin|metformin|insulin|chemotherapy|radiation|surgery)\b",
            r"\b(?:mg|mcg|ml|units|daily|twice|weekly|monthly)\b",
            # Medical procedures and tests
            r"\b(?:CT scan|MRI|X-ray|ultrasound|biopsy|surgery|operation)\b",
            r"\b(?:blood pressure|heart rate|temperature|oxygen|pulse)\b",
            # Time references (not specific dates)
            r"\b(?:weeks?|months?|years?|ago|prior|before|after|during)\b",
            r"\b(?:recent|acute|chronic|stable|improving|worsening)\b",
            # Care planning terms
            r"\b(?:comfort care|palliative|hospice|home care|family)\b",
            r"\b(?:side effects|performance status|quality of life)\b",
            # Medical measurements and values
            r"\b(?:normal|abnormal|elevated|decreased|positive|negative)\b",
            r"\b(?:mild|moderate|severe|stable|improved|deteriorated)\b",
        ]

        import re

        filtered_entities = []

        for entity in entities:
            entity_text = text[entity.start : entity.end].lower()
            is_clinical = False

            # Check if entity text matches clinical patterns
            for pattern in clinical_patterns:
                if re.search(pattern, entity_text, re.IGNORECASE):
                    is_clinical = True
                    break

            # Only keep non-clinical entities
            if not is_clinical:
                filtered_entities.append(entity)

        return filtered_entities

    def _create_audit_trail(self, entities: List[PHIEntity]) -> List[Dict]:
        """
        Create audit trail from detected entities.

        Generates a sanitized audit record without exposing actual PHI values.
        Useful for compliance reporting and quality assurance.

        Args:
            entities: Detected PHI entities

        Returns:
            List of audit records (position, category, confidence)
        """
        audit = [
            {
                "start": entity.start,
                "end": entity.end,
                "category": entity.category,
                "confidence": round(entity.confidence, 3),
            }
            for entity in entities
        ]
        return audit

    def get_statistics(self) -> Dict:
        """
        Get pipeline processing statistics.

        Returns:
            Dictionary with processing metrics
        """
        return {
            "total_documents_processed": self._stats["total_processed"],
            "total_entities_detected": self._stats["total_entities_detected"],
            "total_entities_redacted": self._stats["total_entities_redacted"],
            "average_entities_per_document": (
                round(
                    self._stats["total_entities_detected"]
                    / self._stats["total_processed"],
                    2,
                )
                if self._stats["total_processed"] > 0
                else 0
            ),
        }

    def reset_statistics(self) -> None:
        """Reset all processing statistics."""
        self._stats = {
            "total_processed": 0,
            "total_entities_detected": 0,
            "total_entities_redacted": 0,
        }
        logger.info("Statistics reset")


# Backward compatibility alias
HIPAADeidentifier = HIPAAPipelineOrchestrator
