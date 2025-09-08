"""
Date Shifting Utilities

Provides functions for shifting dates to maintain relative time relationships
while obscuring actual dates for HIPAA compliance.
"""
import os
import re
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict


def get_date_shift_days_from_config(config: Optional[dict] = None) -> int:
    """
    Gets the number of days to shift dates from centralized configuration.

    Args:
        config: Optional configuration dictionary (deprecated - uses centralized config)

    Returns:
        Number of days to shift as an integer
    """
    # Use centralized configuration system
    from config.config import config as global_config
    return global_config.get_date_shift_days()


def get_consistent_date_shift(salt: str, patient_id: Optional[str] = None) -> int:
    """
    Generate a consistent date shift value for a patient.
    
    This ensures that all dates for the same patient are shifted by the same amount,
    preserving the relative time relationships between events.
    
    Args:
        salt: A salt value for the hash function
        patient_id: Optional patient identifier for consistent shifting
        
    Returns:
        Number of days to shift (between 30 and 90)
    """
    # If no patient ID is provided, use a default value
    if not patient_id:
        patient_id = "default_patient"
        
    # Generate a hash based on the patient ID and salt
    hash_input = f"{patient_id}_{salt}_date_shift"
    hash_bytes = hashlib.sha256(hash_input.encode()).digest()
    
    # Convert first 4 bytes of hash to an integer
    hash_int = int.from_bytes(hash_bytes[:4], byteorder='big')
    
    # Map to a range between 30 and 90 days
    shift_days = 30 + (hash_int % 61)  # 61 = 90 - 30 + 1
    
    return shift_days


def parse_date(date_str: str) -> Tuple[Optional[datetime], Optional[str]]:
    """
    Parse a date string into a datetime object.
    
    Args:
        date_str: The date string to parse
        
    Returns:
        Tuple of (datetime object, format string) if successful, (None, None) otherwise
    """
    if not date_str or not isinstance(date_str, str):
        return None, None
        
    # Strip any leading/trailing whitespace
    date_str = date_str.strip()
    
    # Common date formats to try (from most specific to least specific)
    formats = [
        # ISO format
        "%Y-%m-%d",      # 2023-01-15
        
        # Common US formats
        "%m/%d/%Y",      # 01/15/2023
        "%m/%d/%y",      # 01/15/23
        "%B %d, %Y",     # January 15, 2023
        "%b %d, %Y",     # Jan 15, 2023
        "%m-%d-%Y",      # 01-15-2023
        "%m-%d-%y",      # 01-15-23
        
        # Common UK/European formats
        "%d/%m/%Y",      # 15/01/2023
        "%d/%m/%y",      # 15/01/23
        "%d-%m-%Y",      # 15-01-2023
        "%d-%m-%y",      # 15-01-23
        "%d %B %Y",      # 15 January 2023
        "%d %b %Y",      # 15 Jan 2023
        
        # Other common formats
        "%Y/%m/%d",      # 2023/01/15
        "%Y%m%d",        # 20230115
    ]
    
    # Try each format until one works
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt, fmt
        except ValueError:
            continue
    
    # Try to handle dates with time components
    time_formats = [
        # Date with time
        "%Y-%m-%d %H:%M:%S",     # 2023-01-15 14:30:00
        "%Y-%m-%d %H:%M",        # 2023-01-15 14:30
        "%m/%d/%Y %H:%M:%S",     # 01/15/2023 14:30:00
        "%m/%d/%Y %H:%M",        # 01/15/2023 14:30
        "%d/%m/%Y %H:%M:%S",     # 15/01/2023 14:30:00
        "%d/%m/%Y %H:%M",        # 15/01/2023 14:30
    ]
    
    for fmt in time_formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt, fmt
        except ValueError:
            continue
            
    # If it looks like a date but no format matches, try to extract year, month, day
    date_pattern = re.compile(r'(\d{1,4})[-/\s](\d{1,2})[-/\s](\d{1,4})')
    match = date_pattern.search(date_str)
    
    if match:
        # Try to determine which part is year, month, day based on values
        parts = [match.group(1), match.group(2), match.group(3)]
        
        # If one part is clearly a year (4 digits or >31)
        for i, part in enumerate(parts):
            if len(part) == 4 or int(part) > 31:
                # This is likely the year
                try:
                    year = int(part)
                    # Assume the other parts are month and day in some order
                    month = int(parts[(i+1) % 3])
                    day = int(parts[(i+2) % 3])
                    
                    if month > 12:  # Swap month and day if month is invalid
                        month, day = day, month
                        
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        try:
                            dt = datetime(year, month, day)
                            # Create a custom format string based on the original pattern
                            fmt = "custom"
                            return dt, fmt
                        except ValueError:
                            pass
                except ValueError:
                    pass
            
    # If no format matches, return None
    return None, None


def shift_date(date_str: str, days: int, patient_id: Optional[str] = None, salt: Optional[str] = None) -> str:
    """
    Shifts a date string by the specified number of days.
    
    Supports multiple common date formats and handles various edge cases.
    
    Args:
        date_str: The date string to shift
        days: Number of days to shift (positive or negative)
        patient_id: Optional patient identifier for consistent shifting
        salt: Optional salt value for consistent shifting
        
    Returns:
        A shifted date string in the same format as the input
    """
    # If salt is provided and patient_id is provided, use consistent shifting
    if salt and patient_id:
        days = get_consistent_date_shift(salt, patient_id)
    
    # Parse the date
    dt, fmt = parse_date(date_str)
    
    # If parsing failed, return the original string instead of placeholder
    if dt is None:
        return date_str  # Don't corrupt the text with placeholders
    
    # Shift the date
    shifted = dt + timedelta(days=days)
    
    # Format the shifted date
    if fmt == "custom":
        # Extract the original pattern and apply it to the shifted date
        date_pattern = re.compile(r'(\d{1,4})[-/\s](\d{1,2})[-/\s](\d{1,4})')
        match = date_pattern.search(date_str)
        
        if match:
            parts = [match.group(1), match.group(2), match.group(3)]
            separators = [
                date_str[len(match.group(1)):len(match.group(1))+1],
                date_str[len(match.group(1))+len(match.group(2))+1:len(match.group(1))+len(match.group(2))+2]
            ]
            
            # Determine which part is year, month, day
            year_idx = -1
            for i, part in enumerate(parts):
                if len(part) == 4 or int(part) > 31:
                    year_idx = i
                    break
            
            if year_idx >= 0:
                # Create the shifted date string with the same format
                result_parts = ["", "", ""]
                result_parts[year_idx] = f"{shifted.year if len(parts[year_idx]) == 4 else shifted.year % 100:0{len(parts[year_idx])}d}"
                result_parts[(year_idx+1) % 3] = f"{shifted.month:0{len(parts[(year_idx+1) % 3])}d}"
                result_parts[(year_idx+2) % 3] = f"{shifted.day:0{len(parts[(year_idx+2) % 3])}d}"
                
                return result_parts[0] + separators[0] + result_parts[1] + separators[1] + result_parts[2]
    
    # Use the standard format
    try:
        return shifted.strftime(fmt)
    except:
        return date_str  # Return original if formatting fails


class DateShifter:
    """
    Class to manage date shifting with consistent patient-specific offsets.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize the date shifter.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.salt = config.get("security", {}).get("salt", "default_salt")
        self.default_shift_days = get_date_shift_days_from_config(config)
        self.patient_shifts = {}  # Cache of patient-specific shift days
        
    def get_shift_days(self, patient_id: Optional[str] = None) -> int:
        """
        Get the number of days to shift for a specific patient.
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            Number of days to shift
        """
        if not patient_id:
            return self.default_shift_days
            
        # Use cached value if available
        if patient_id in self.patient_shifts:
            return self.patient_shifts[patient_id]
            
        # Generate a new shift value and cache it
        shift_days = get_consistent_date_shift(self.salt, patient_id)
        self.patient_shifts[patient_id] = shift_days
        return shift_days
        
    def shift_date(self, date_str: str, patient_id: Optional[str] = None) -> str:
        """
        Shift a date string using patient-specific offset.
        
        Args:
            date_str: Date string to shift
            patient_id: Patient identifier
            
        Returns:
            Shifted date string
        """
        # Fix issue #6: Dates Shifted/Mutated inconsistently
        # Create a cache key for consistent date shifting
        cache_key = f"{date_str}:{patient_id or 'default'}"
        
        # Use cached value if available
        if hasattr(self, 'date_cache') and cache_key in self.date_cache:
            return self.date_cache[cache_key]
            
        # Initialize cache if not exists
        if not hasattr(self, 'date_cache'):
            self.date_cache = {}
            
        # Get shift days and apply shift
        shift_days = self.get_shift_days(patient_id)
        result = shift_date(date_str, shift_days, patient_id, self.salt)
        
        # Cache the result for consistency
        self.date_cache[cache_key] = result
        return result