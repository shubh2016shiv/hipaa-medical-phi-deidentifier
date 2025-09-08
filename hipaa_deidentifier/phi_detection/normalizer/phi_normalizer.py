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

Hinglish Comments:

Ye hamara Stage 0 normalization layer hai jo text ko normalize karta hai bina original text ko modify kiye.
Iska main purpose hai OCR artifacts aur Unicode issues ko fix karna taaki detection models better kaam kar sakein.

Ye implementation production-ready hai aur following features provide karta hai:

1. Unicode NFKC Normalization - Different types ke quotes, accents, width variants ko normalize karta hai
2. Confusable Character Folding - OCR mistakes jaise "0↔O", "l↔1", curly quotes ko fix karta hai  
3. Space/Punctuation Normalization - Repeated spaces, hyphens, punctuation ko clean karta hai
4. De-hyphenation - OCR line-wrap artifacts ko fix karta hai
5. OCR Header Token Fixing - DOB vs D0B, MRN etc. ko fix karta hai
6. Character Mapping - Har normalized character ka exact position original text mein track karta hai
7. Container Detection - URLs aur filenames ko early detect karta hai

Ye approach non-destructive hai - original text untouched rehta hai, sirf working copy create hoti hai.
"""

import re
import unicodedata
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass


@dataclass
class NormalizedText:
    """
    Container for normalized text and character mapping information.
    
    Attributes:
        original: The original input text
        normalized: The canonicalized working copy
        map_back: Mapping from normalized positions to original positions
        project_fn: Function to project spans from normalized to original
    """
    original: str
    normalized: str
    map_back: List[int]  # normalized_index -> original_index
    
    def project(self, a_norm: int, b_norm: int) -> Tuple[int, int]:
        """
        Project a span from normalized text back to original text.
        
        Args:
            a_norm: Start position in normalized text
            b_norm: End position in normalized text
            
        Returns:
            (a_orig, b_orig) positions in original text
        """
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
        # Confusable character mappings
        self.CONFUSABLE_MAP = {
            "\u2018": "'",  # Left single quotation mark
            "\u2019": "'",  # Right single quotation mark
            "\u201C": '"',  # Left double quotation mark
            "\u201D": '"',  # Right double quotation mark
            "\u2013": "-",  # En dash
            "\u2014": "-",  # Em dash
            "\u2212": "-",  # Minus sign
            "\u00A0": " ",  # Non-breaking space
        }
        
        # OCR confusable character mappings for common OCR errors
        self.OCR_CONFUSABLE_MAP = {
            "0": "1",  # Common OCR error: 0 looks like 1
            "l": "1",  # Common OCR error: l looks like 1  
            "O": "0",  # Common OCR error: O looks like 0
            "I": "1",  # Common OCR error: I looks like 1
        }
        
        # OCR header tokens for fixing common OCR mistakes
        self.OCR_HEADER_TOKENS = {"DOB", "D0B", "MRN", "ACC", "ACCOUNT", "HICN", "PLAN", "ID", "SSN"}
        
        # Compiled regex patterns
        self.RX_URL = re.compile(r"https?://\S+", re.IGNORECASE)
        self.RX_FILENAME = re.compile(r"\b[\w.-]+\.(pdf|png|jpg|jpeg|tif|tiff|txt|rtf|docx)\b", re.IGNORECASE)
        self.RX_SPACES3 = re.compile(r"[ \t]{3,}")
        self.RX_PADDEDSEP = re.compile(r"\s*([.\-/])\s*")
        self.RX_WRAP_HYPH = re.compile(r"([A-Za-z])-\s+([A-Za-z])")
        
        # OCR date pattern fixing
        self.RX_OCR_DATE_1 = re.compile(r'\b0l/(\d+)/(\d{4})\b')  # 0l/15/1980 -> 01/15/1980
        self.RX_OCR_DATE_2 = re.compile(r'\b(\d+)/0l/(\d{4})\b')  # 15/0l/1980 -> 15/01/1980
        self.RX_OCR_DATE_3 = re.compile(r'\b0l/0l/(\d{4})\b')     # 0l/0l/1980 -> 01/01/1980
    
    def normalize_with_map(self, s: str) -> NormalizedText:
        """
        Normalize text while maintaining character mapping to original.
        
        This is the main normalization function that follows the pseudocode exactly.
        
        Args:
            s: The original text to normalize
            
        Returns:
            NormalizedText object containing normalized text and mapping information
        """
        # Step 1: Unicode NFKC normalization
        s_nfkc = unicodedata.normalize('NFKC', s)
        
        out_chars = []
        map_back = []
        
        # Step 2: Fold confusables, drop zero-width/control (keep mapping consistent)
        for i, ch in enumerate(s_nfkc):
            ch = self.CONFUSABLE_MAP.get(ch, ch)
            # Apply OCR confusable character fixing
            ch = self._apply_ocr_confusable_char(ch)
            if self._is_control_or_zerowidth(ch) and ch not in {"\n", "\t"}:
                continue  # skip char; do not append; no map entry
            out_chars.append(ch)
            map_back.append(i)
        
        norm = ''.join(out_chars)
        
        # Step 3: Collapse excessive whitespace and padded separators
        norm, map_back = self._collapse_with_map(norm, map_back, self.RX_SPACES3, " ")
        # For padded separators, we need to handle the replacement differently
        norm, map_back = self._collapse_padded_separators(norm, map_back)
        
        # Step 4: De-hyphenation across wrapped lines (bounded iterations to avoid loops)
        for _ in range(2):  # Maximum 2 iterations
            m = self.RX_WRAP_HYPH.search(norm)
            if m is None:
                break
            
            # Remove the "-<spaces>" region between m.group(1) end and m.group(2) start
            a = m.end(1)  # position right after first letter
            b = m.start(2)  # position at second letter
            norm = norm[:a] + norm[b:]
            map_back = map_back[:a] + map_back[b:]
        
        # Step 4.5: OCR date pattern fixing
        norm, map_back = self._fix_ocr_date_patterns(norm, map_back)
        
        # Step 5: Token-aware OCR header fixes
        norm, map_back = self._fix_ocr_header_tokens(norm, map_back)
        
        return NormalizedText(original=s, normalized=norm, map_back=map_back)
    
    def _is_control_or_zerowidth(self, ch: str) -> bool:
        """Check if character is control or zero-width character."""
        return unicodedata.category(ch) in ['Cc', 'Cf', 'Cs'] or ch in ['\u200b', '\u200c', '\u200d']
    
    def _apply_ocr_confusable_char(self, ch: str) -> str:
        """
        Apply OCR confusable character fixing to a single character.
        
        This method uses heuristics to determine when to apply OCR confusable
        character mappings based on context.
        
        Args:
            ch: Single character to potentially fix
            
        Returns:
            Fixed character or original if no fix needed
        """
        # For now, don't apply OCR confusable mapping at character level
        # This should be handled at the token level in _fix_ocr_header_tokens
        # to avoid over-correction
        return ch
    
    def _collapse_with_map(self, text: str, mb: List[int], regex: re.Pattern, replacement: str) -> Tuple[str, List[int]]:
        """
        Collapse regex matches while maintaining character mapping.
        
        Args:
            text: The text to process
            mb: Current mapping from normalized to original positions
            regex: Compiled regex pattern to match
            replacement: Replacement string
            
        Returns:
            (new_text, new_mapping) tuple
        """
        out_text = []
        out_map = []
        last = 0
        
        for m in regex.finditer(text):
            # Keep [last, m.start())
            out_text.append(text[last:m.start()])
            out_map.extend(mb[last:m.start()])
            
            # Add replacement, anchor map to first char of the match
            out_text.append(replacement)
            if len(replacement) > 0:
                out_map.append(mb[m.start()])
            
            last = m.end()
        
        # Add tail
        out_text.append(text[last:])
        out_map.extend(mb[last:])
        
        return (''.join(out_text), out_map)
    
    def _collapse_padded_separators(self, text: str, mb: List[int]) -> Tuple[str, List[int]]:
        """
        Collapse padded separators while maintaining character mapping.
        
        Args:
            text: The text to process
            mb: Current mapping from normalized to original positions
            
        Returns:
            (new_text, new_mapping) tuple
        """
        out_text = []
        out_map = []
        last = 0
        
        for m in self.RX_PADDEDSEP.finditer(text):
            # Keep [last, m.start())
            out_text.append(text[last:m.start()])
            out_map.extend(mb[last:m.start()])
            
            # Add the separator without padding
            separator = m.group(1)
            out_text.append(separator)
            out_map.append(mb[m.start()])
            
            last = m.end()
        
        # Add tail
        out_text.append(text[last:])
        out_map.extend(mb[last:])
        
        return (''.join(out_text), out_map)
    
    def _fix_ocr_date_patterns(self, text: str, mb: List[int]) -> Tuple[str, List[int]]:
        """
        Fix OCR date patterns while maintaining character mapping.
        
        Args:
            text: The text to process
            mb: Current mapping from normalized to original positions
            
        Returns:
            (new_text, new_mapping) tuple
        """
        out_text = []
        out_map = []
        last = 0
        
        # Apply OCR date pattern fixes
        patterns = [
            (self.RX_OCR_DATE_1, r'01/\1/\2'),  # 0l/15/1980 -> 01/15/1980
            (self.RX_OCR_DATE_2, r'\1/01/\2'),  # 15/0l/1980 -> 15/01/1980
            (self.RX_OCR_DATE_3, r'01/01/\1'),  # 0l/0l/1980 -> 01/01/1980
        ]
        
        for regex, replacement in patterns:
            for m in regex.finditer(text):
                # Keep [last, m.start())
                out_text.append(text[last:m.start()])
                out_map.extend(mb[last:m.start()])
                
                # Add replacement
                replacement_text = m.expand(replacement)
                out_text.append(replacement_text)
                
                # Map replacement to original position
                for _ in range(len(replacement_text)):
                    out_map.append(mb[m.start()])
                
                last = m.end()
        
        # Add tail
        out_text.append(text[last:])
        out_map.extend(mb[last:])
        
        return (''.join(out_text), out_map)
    
    def _fix_ocr_header_tokens(self, norm: str, map_back: List[int]) -> Tuple[str, List[int]]:
        """
        Fix OCR header tokens like DOB vs D0B, MRN etc.
        
        Args:
            norm: Normalized text
            map_back: Current mapping
            
        Returns:
            (fixed_text, updated_mapping) tuple
        """
        # Tokenize by word boundaries
        tokens = list(re.finditer(r'\b\w+\b', norm))
        if not tokens:
            return norm, map_back
        
        rebuilt = []
        new_map = []
        index_cursor = 0
        
        for t in tokens:
            t_text = t.group()
            t_start = t.start()
            t_end = t.end()
            
            # Fix OCR header token
            fixed = self._fix_ocr_header_token(t_text, self.OCR_HEADER_TOKENS)
            rebuilt.append(fixed)
            
            # Map segment: if length same, map_back segment 1:1; if different length,
            # still point the new chars to the first original index of the token
            if len(fixed) == (t_end - t_start):
                new_map.extend(map_back[t_start:t_end])
            else:
                for _ in range(len(fixed)):
                    new_map.append(map_back[t_start])
            
            # Add following delimiter (space, punctuation) intact
            # Find next token or end of string
            next_token_start = len(norm)
            for next_t in tokens:
                if next_t.start() > t_end:
                    next_token_start = next_t.start()
                    break
            
            delim = norm[t_end:next_token_start]
            rebuilt.append(delim)
            new_map.extend(map_back[t_end:t_end + len(delim)])
            index_cursor = t_end + len(delim)
        
        if rebuilt:
            return (''.join(rebuilt), new_map)
        
        return norm, map_back
    
    def _fix_ocr_header_token(self, tok: str, headers: set) -> str:
        """
        Fix OCR header token using heuristics.
        
        Args:
            tok: Token to fix
            headers: Set of known header tokens
            
        Returns:
            Fixed token
        """
        # Heuristic: if token is short (2–10), uppercase, contains letters/digits
        # and resembles any header, fix common confusions
        if 2 <= len(tok) <= 10 and self._is_upper_or_apostrophe(tok):
            t = tok
            
            # Fix common OCR confusables in header tokens
            if any(h in tok for h in ["DOB", "D0B"]):
                t = t.replace("0", "O")  # D0B -> DOB
            elif any(h in tok for h in ["MRN", "PATIENT", "PATlENT"]):
                # Fix common OCR errors in MRN and PATIENT
                t = t.replace("l", "I")  # PATlENT -> PATIENT
                t = t.replace("0", "O")  # MRN with 0 -> O
            elif any(h in tok for h in ["SN", "DEVICE"]):
                # Fix device serial numbers
                t = t.replace("l", "1")  # SN-MD00l -> SN-MD001
                t = t.replace("0", "1")  # Common OCR error in numbers
            
            # Avoid changing pure numbers or long alnums
            return t
        return tok
    
    def _is_upper_or_apostrophe(self, tok: str) -> bool:
        """Check if token is uppercase or contains apostrophes."""
        return tok.isupper() or "'" in tok
    
    def find_url_spans(self, norm_text: str) -> List[Tuple[int, int]]:
        """
        Find URL spans in normalized text.
        
        Args:
            norm_text: Normalized text
            
        Returns:
            List of (start, end) spans for URLs
        """
        spans = []
        for m in self.RX_URL.finditer(norm_text):
            spans.append((m.start(), m.end()))
        return spans
    
    def find_filename_spans(self, norm_text: str) -> List[Tuple[int, int]]:
        """
        Find filename spans in normalized text.
        
        Args:
            norm_text: Normalized text
            
        Returns:
            List of (start, end) spans for filenames
        """
        spans = []
        for m in self.RX_FILENAME.finditer(norm_text):
            spans.append((m.start(), m.end()))
        return spans
    
    def stage0_normalize_and_candidates(self, original_text: str) -> Dict:
        """
        Stage 0 normalization with container detection.
        
        This is the main entry point for the normalization pipeline.
        
        Args:
            original_text: The original text to normalize
            
        Returns:
            Dictionary containing normalized text, mapping, and container spans
        """
        n = self.normalize_with_map(original_text)
        
        url_spans_norm = self.find_url_spans(n.normalized)
        filename_spans_norm = self.find_filename_spans(n.normalized)
        
        return {
            "normalized_text": n.normalized,
            "map_back": n.map_back,
            "project_fn": n.project,  # callback to map spans back
            "containers": {
                "urls": url_spans_norm,
                "filenames": filename_spans_norm
            }
        }


# Backward compatibility alias
TextNormalizer = Stage0Normalizer
