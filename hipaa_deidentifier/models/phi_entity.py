"""
PHI Entity Model

Defines the data structures for representing detected PHI entities.
"""
from dataclasses import dataclass
from typing import List


@dataclass
class PHIEntity:
    """
    Represents a detected Protected Health Information (PHI) entity in text.
    
    Attributes:
        start: Start position of the entity in the text
        end: End position of the entity in the text
        category: Category of PHI (e.g., NAME, MRN, SSN)
        confidence: Confidence score of the detection (0.0 to 1.0)
        text: The actual text content of the entity
    """
    start: int
    end: int
    category: str
    confidence: float
    text: str


def merge_overlapping_entities(rule_entities: List[PHIEntity], ml_entities: List[PHIEntity]) -> List[PHIEntity]:
    """
    Merges potentially overlapping PHI entities from different detection methods.
    
    When entities overlap:
    1. If they have the same category, merge them with expanded boundaries
    2. If they have different categories, keep both unless they have significant overlap
    3. For significant overlaps of different categories, prefer the one with higher confidence
    
    Args:
        rule_entities: Entities detected by rule-based methods
        ml_entities: Entities detected by machine learning methods
        
    Returns:
        A list of merged PHI entities with resolved overlaps
    """
    # Combine all entities and sort by start position (and end position for ties)
    all_entities = rule_entities + ml_entities
    all_entities.sort(key=lambda e: (e.start, -e.end))
    
    # No entities to merge
    if not all_entities:
        return []
        
    # Function to calculate overlap percentage
    def overlap_percent(e1, e2):
        overlap_start = max(e1.start, e2.start)
        overlap_end = min(e1.end, e2.end)
        
        if overlap_start >= overlap_end:  # No overlap
            return 0.0
            
        overlap_length = overlap_end - overlap_start
        e1_length = e1.end - e1.start
        e2_length = e2.end - e2.start
        
        # Return the maximum percentage of overlap relative to either entity
        return max(overlap_length / e1_length, overlap_length / e2_length) if e1_length > 0 and e2_length > 0 else 0.0
    
    # Process entities one by one
    merged = [all_entities[0]]  # Start with the first entity
    
    for entity in all_entities[1:]:
        # Check for overlaps with existing merged entities
        overlapping = False
        
        for i, existing in enumerate(merged):
            # Calculate overlap percentage
            overlap = overlap_percent(entity, existing)
            
            # If significant overlap (>50%)
            if overlap > 0.5:
                overlapping = True
                
                # Same category - merge them
                if entity.category == existing.category:
                    # Create new entity with expanded boundaries and max confidence
                    merged[i] = PHIEntity(
                        start=min(existing.start, entity.start),
                        end=max(existing.end, entity.end),
                        category=existing.category,
                        confidence=max(existing.confidence, entity.confidence),
                        text=entity.text if entity.text else existing.text  # Keep text if available
                    )
                # Different categories - take the one with higher confidence
                elif entity.confidence > existing.confidence:
                    merged[i] = entity
                # Otherwise keep the existing one
                break
        
        # If no significant overlap found, add as a new entity
        if not overlapping:
            merged.append(entity)
    
    # Make sure all entities have text populated for redaction
    for i, entity in enumerate(merged):
        if not entity.text:
            # This should not happen with the improved logic, but just in case
            merged[i] = PHIEntity(
                start=entity.start,
                end=entity.end,
                category=entity.category,
                confidence=entity.confidence,
                text="[UNKNOWN]"  # Placeholder for missing text
            )
            
    return merged


