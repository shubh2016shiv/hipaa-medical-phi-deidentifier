"""
Stage 0: Non-destructive Text Normalization & Span Mapping

Implementation of the robust normalization layer based on the provided pseudocode.
This module provides the foundational normalization that creates a canonicalized
working copy of text while maintaining precise character mapping back to the original.

Goals:
1. Create norm_text that is easier for regex + NER to recognize
2. Maintain map_back so every detected span can be projected back to original text
3. Eliminate most partial redactions and OCR misses
4. Provide a single, precise redaction pass
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .normalizer_config import (
    CharacterMappings,
    NormalizationPatterns,
    NormalizationSettings,
    OCRPatterns,
)


@dataclass
class NormalizedText:
    """
    Container for normalized text and character mapping information.

    Attributes:
        original: The original input text
        normalized: The canonicalized working copy
        map_back: Mapping from normalized positions to original positions
    """

    original: str
    normalized: str
    map_back: List[int]  # normalized_index -> original_index

    def project(self, a_norm: int, b_norm: int) -> Tuple[int, int]:
        """Project a span from normalized text back to original text."""
        b_norm = min(b_norm, len(self.map_back))
        if a_norm >= len(self.map_back):
            return (len(self.original), len(self.original))
        return (self.map_back[a_norm], self.map_back[b_norm - 1] + 1)


class Stage0Normalizer:
    """
    Stage 0 normalizer that creates canonicalized working copies
    while maintaining precise character mapping to the original text.

    This implementation follows the provided pseudocode exactly for maximum
    reliability and consistency with the design specifications.
    """

    def __init__(self):
        """Initialize the Stage 0 normalizer with compiled patterns."""
        self.CONFUSABLE_MAP = CharacterMappings.UNICODE_CONFUSABLES
        self.OCR_HEADER_TOKENS = OCRPatterns.HEADER_TOKENS

        # Compiled regex patterns
        self.RX_URL = re.compile(NormalizationPatterns.URL_PATTERN, re.IGNORECASE)
        self.RX_FILENAME = re.compile(
            NormalizationPatterns.FILENAME_PATTERN, re.IGNORECASE
        )
        self.RX_SPACES3 = re.compile(NormalizationPatterns.MULTIPLE_SPACES)
        self.RX_PADDEDSEP = re.compile(NormalizationPatterns.PADDED_SEPARATOR)
        self.RX_WRAP_HYPH = re.compile(NormalizationPatterns.WRAP_HYPHEN)
        self.RX_WORD = re.compile(NormalizationPatterns.WORD_BOUNDARY)

        # Compiled OCR date patterns
        self.ocr_date_patterns = [
            (re.compile(pattern), replacement)
            for pattern, replacement in OCRPatterns.DATE_PATTERNS
        ]

    def normalize_with_map(self, s: str) -> NormalizedText:
        """
        Normalize text while maintaining character mapping to original.

        Args:
            s: The original text to normalize

        Returns:
            NormalizedText object containing normalized text and mapping information
        """
        # Step 1: Unicode NFKC normalization
        s_nfkc = unicodedata.normalize(NormalizationSettings.UNICODE_FORM, s)

        out_chars = []
        map_back = []

        # Step 2: Fold confusables, drop zero-width/control (keep mapping consistent)
        for i, ch in enumerate(s_nfkc):
            ch = self.CONFUSABLE_MAP.get(ch, ch)
            if (
                self._is_control_or_zerowidth(ch)
                and ch not in NormalizationSettings.PRESERVED_CONTROL_CHARS
            ):
                continue
            out_chars.append(ch)
            map_back.append(i)

        norm = "".join(out_chars)

        # Step 3: Collapse excessive whitespace and padded separators
        norm, map_back = self._collapse_with_map(norm, map_back, self.RX_SPACES3, " ")
        norm, map_back = self._collapse_padded_separators(norm, map_back)

        # Step 4: De-hyphenation across wrapped lines (bounded iterations to avoid loops)
        for _ in range(NormalizationSettings.MAX_DEHYPHENATION_ITERATIONS):
            m = self.RX_WRAP_HYPH.search(norm)
            if m is None:
                break
            a = m.end(1)
            b = m.start(2)
            norm = norm[:a] + norm[b:]
            map_back = map_back[:a] + map_back[b:]

        # Step 4.5: OCR date pattern fixing
        norm, map_back = self._fix_ocr_date_patterns(norm, map_back)

        # Step 5: Token-aware OCR header fixes
        norm, map_back = self._fix_ocr_header_tokens(norm, map_back)

        return NormalizedText(original=s, normalized=norm, map_back=map_back)

    def _is_control_or_zerowidth(self, ch: str) -> bool:
        """Check if character is control or zero-width character."""
        return (
            unicodedata.category(ch) in CharacterMappings.CONTROL_CATEGORIES
            or ch in CharacterMappings.ZERO_WIDTH_CHARS
        )

    def _collapse_with_map(
        self, text: str, mb: List[int], regex: re.Pattern, replacement: str
    ) -> Tuple[str, List[int]]:
        """Collapse regex matches while maintaining character mapping."""
        out_text = []
        out_map = []
        last = 0

        for m in regex.finditer(text):
            out_text.append(text[last : m.start()])
            out_map.extend(mb[last : m.start()])
            out_text.append(replacement)
            if len(replacement) > 0:
                out_map.append(mb[m.start()])
            last = m.end()

        out_text.append(text[last:])
        out_map.extend(mb[last:])

        return ("".join(out_text), out_map)

    def _collapse_padded_separators(
        self, text: str, mb: List[int]
    ) -> Tuple[str, List[int]]:
        """Collapse padded separators while maintaining character mapping."""
        out_text = []
        out_map = []
        last = 0

        for m in self.RX_PADDEDSEP.finditer(text):
            out_text.append(text[last : m.start()])
            out_map.extend(mb[last : m.start()])
            separator = m.group(1)
            out_text.append(separator)
            out_map.append(mb[m.start()])
            last = m.end()

        out_text.append(text[last:])
        out_map.extend(mb[last:])

        return ("".join(out_text), out_map)

    def _fix_ocr_date_patterns(self, text: str, mb: List[int]) -> Tuple[str, List[int]]:
        """Fix OCR date patterns while maintaining character mapping."""
        out_text = []
        out_map = []
        last = 0

        for regex, replacement in self.ocr_date_patterns:
            for m in regex.finditer(text):
                out_text.append(text[last : m.start()])
                out_map.extend(mb[last : m.start()])
                replacement_text = m.expand(replacement)
                out_text.append(replacement_text)
                for _ in range(len(replacement_text)):
                    out_map.append(mb[m.start()])
                last = m.end()

        out_text.append(text[last:])
        out_map.extend(mb[last:])

        return ("".join(out_text), out_map)

    def _fix_ocr_header_tokens(
        self, norm: str, map_back: List[int]
    ) -> Tuple[str, List[int]]:
        """Fix OCR header tokens like DOB vs D0B, MRN etc."""
        tokens = list(self.RX_WORD.finditer(norm))
        if not tokens:
            return norm, map_back

        rebuilt = []
        new_map = []

        for t in tokens:
            t_text = t.group()
            t_start = t.start()
            t_end = t.end()

            fixed = self._fix_ocr_header_token(t_text, self.OCR_HEADER_TOKENS)
            rebuilt.append(fixed)

            if len(fixed) == (t_end - t_start):
                new_map.extend(map_back[t_start:t_end])
            else:
                for _ in range(len(fixed)):
                    new_map.append(map_back[t_start])

            next_token_start = len(norm)
            for next_t in tokens:
                if next_t.start() > t_end:
                    next_token_start = next_t.start()
                    break

            delim = norm[t_end:next_token_start]
            rebuilt.append(delim)
            new_map.extend(map_back[t_end : t_end + len(delim)])

        if rebuilt:
            return ("".join(rebuilt), new_map)

        return norm, map_back

    def _fix_ocr_header_token(self, tok: str, headers: set) -> str:
        """Fix OCR header token using heuristics."""
        min_len = NormalizationSettings.MIN_HEADER_TOKEN_LENGTH
        max_len = NormalizationSettings.MAX_HEADER_TOKEN_LENGTH

        if min_len <= len(tok) <= max_len and self._is_upper_or_apostrophe(tok):
            t = tok
            if any(h in tok for h in ["DOB", "D0B"]):
                t = t.replace("0", "O")
            elif any(h in tok for h in ["MRN", "PATIENT", "PATlENT"]):
                t = t.replace("l", "I")
                t = t.replace("0", "O")
            elif any(h in tok for h in ["SN", "DEVICE"]):
                t = t.replace("l", "1")
                t = t.replace("0", "1")
            return t
        return tok

    def _is_upper_or_apostrophe(self, tok: str) -> bool:
        """Check if token is uppercase or contains apostrophes."""
        return tok.isupper() or "'" in tok

    def find_url_spans(self, norm_text: str) -> List[Tuple[int, int]]:
        """Find URL spans in normalized text."""
        return [(m.start(), m.end()) for m in self.RX_URL.finditer(norm_text)]

    def find_filename_spans(self, norm_text: str) -> List[Tuple[int, int]]:
        """Find filename spans in normalized text."""
        return [(m.start(), m.end()) for m in self.RX_FILENAME.finditer(norm_text)]

    def stage0_normalize_and_candidates(self, original_text: str) -> Dict:
        """
        Stage 0 normalization with container detection.

        Returns:
            Dictionary containing normalized text, mapping, and container spans
        """
        n = self.normalize_with_map(original_text)

        return {
            "normalized_text": n.normalized,
            "map_back": n.map_back,
            "project_fn": n.project,
            "containers": {
                "urls": self.find_url_spans(n.normalized),
                "filenames": self.find_filename_spans(n.normalized),
            },
        }


# Backward compatibility alias
TextNormalizer = Stage0Normalizer
