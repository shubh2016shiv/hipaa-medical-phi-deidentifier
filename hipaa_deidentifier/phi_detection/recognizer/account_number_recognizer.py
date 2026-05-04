"""
Account Number Recognizer — Detects financial account numbers in clinical text.

Architecture:
-------------
    ┌─────────────────────────┐     ┌──────────────────────────────┐
    │  PresidioIdentifier     │────▶│  AccountNumberRecognizer     │
    │  (identifier/)          │     │  (recognizer/)               │
    └─────────────────────────┘     └──────────────────────────────┘

    Registered with Presidio's AnalyzerEngine registry.
    Fires on ACCOUNT_NUMBER entity type.

    Covers HIPAA Safe Harbor identifier #8: account numbers.

Dependencies:
    - recognizer_config.py  — RecognizerThresholds constants
    - utils/logger.py       — Structured logging

Author: HIPAA De-identification System
Last Updated: 2026-05-02
"""

from __future__ import annotations

from typing import List, Optional

from presidio_analyzer import Pattern, PatternRecognizer

from ...utils.logger import get_logger
from .recognizer_config import RecognizerThresholds

logger = get_logger("recognizer.account_number")


class AccountNumberRecognizer(PatternRecognizer):
    """Recognizes financial account numbers in clinical and administrative text.

    Detects patterns such as:
    - Account Number: ACC-123456
    - Bank Account: 98765432101
    - Financial ID: FIN-ABC987

    Example:
        >>> recognizer = AccountNumberRecognizer()
        >>> results = recognizer.analyze("Account #: ACC-123456", ["ACCOUNT_NUMBER"], None)
        >>> print(len(results))
        1
    """

    def __init__(
        self,
        name: str = "ACCOUNT_NUMBER",
        supported_entity: str = "ACCOUNT_NUMBER",
        patterns: Optional[List[Pattern]] = None,
    ) -> None:
        """Initialize the account number recognizer.

        Args:
            name: Recognizer name for Presidio registry.
            supported_entity: Entity type emitted on detection.
            patterns: Optional custom patterns; defaults are used when None.
        """
        if patterns is None:
            patterns = [
                # FIN (Financial Identity Number) — the standard hospital billing
                # account number in Epic/Cerner/Meditech.  Appears as "FIN: FIN-XXXXXXXXX"
                # or "FIN Number: FIN-XXXXXXXXX" in virtually every inpatient note header.
                Pattern(
                    "fin_labeled",
                    r"\bFIN\s*(?:Number|No\.?|ID|#)?\s*[:#=\-]?\s*(?:FIN[-])?([0-9]{6,15})\b",
                    RecognizerThresholds.VERY_HIGH_CONFIDENCE,
                ),
                Pattern(
                    "fin_prefixed",
                    r"\bFIN-([0-9]{6,15})\b",
                    RecognizerThresholds.HIGH_CONFIDENCE,
                ),
                # Generic labeled account numbers (banking/administrative)
                Pattern(
                    "account_number_labeled",
                    r"\b(?:Account|Acct|Bank|Financial|Payment)\s*(?:Number|ID|#)?\s*[:#=\-]?\s*([A-Z0-9\-]{6,20})\b",
                    RecognizerThresholds.HIGH_CONFIDENCE,
                ),
                Pattern(
                    "account_number_acc_prefixed",
                    r"\bACC[-#]?([A-Z0-9\-]{6,15})\b",
                    RecognizerThresholds.MEDIUM_HIGH_CONFIDENCE,
                ),
                Pattern(
                    "bank_account_labeled",
                    r"\bBank\s*(?:Account|Acct|#)?\s*[:#=\-]?\s*([0-9]{8,20})\b",
                    RecognizerThresholds.MEDIUM_CONFIDENCE,
                ),
            ]

        super().__init__(
            supported_entity=supported_entity, patterns=patterns, name=name
        )
        logger.info(
            "AccountNumberRecognizer initialized with %d patterns", len(patterns)
        )
