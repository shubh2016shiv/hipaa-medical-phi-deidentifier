#!/usr/bin/env python3
"""
Base Identifier Abstract Class

Defines the interface that all PHI identifier implementations must follow.
This ensures consistent behavior and makes it easy to add new identifier types.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from hipaa_deidentifier.models.phi_entity import PHIEntity


class BaseIdentifier(ABC):
    """
    Abstract base class for all PHI identifiers.

    Defines the contract that all identifier implementations must follow,
    ensuring consistent interface and behavior across the detection pipeline.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self._validate_config()

    @abstractmethod
    def detect(self, text: str) -> List[PHIEntity]:
        """
        Detect PHI entities in the given text.

        Args:
            text: The input text to analyze for PHI entities

        Returns:
            List of detected PHI entities with their locations and metadata
        """
        pass

    def _validate_config(self) -> None:
        """Override in subclasses to implement custom validation logic."""
        pass

    def get_supported_entities(self) -> set:
        """Return the set of entity types supported by this identifier."""
        return getattr(self, 'SUPPORTED_IDENTIFIERS', set())

    def get_identifier_name(self) -> str:
        """Return the name of this identifier for logging and tracking."""
        return self.__class__.__name__
