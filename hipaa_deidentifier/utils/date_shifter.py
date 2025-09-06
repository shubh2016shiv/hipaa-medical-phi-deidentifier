"""
Date Shifting Utilities

Provides functions for shifting dates to maintain relative time relationships
while obscuring actual dates for HIPAA compliance.
"""
import os
from datetime import datetime, timedelta


def get_date_shift_days_from_config(config: dict) -> int:
    """
    Gets the number of days to shift dates from configuration.
    
    Args:
        config: The configuration dictionary
        
    Returns:
        Number of days to shift as an integer
    """
    return config.get("security", {}).get("date_shift_days", 30)


def shift_date(date_str: str, days: int) -> str:
    """
    Shifts a date string by the specified number of days.
    
    Supports multiple common date formats and handles various edge cases.
    
    Args:
        date_str: The date string to shift
        days: Number of days to shift (positive or negative)
        
    Returns:
        A shifted date string in the same format as the input
    """
    if not date_str or not isinstance(date_str, str):
        return "[REDACTED-DATE]"
        
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
            shifted = dt + timedelta(days=days)
            return shifted.strftime(fmt)
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
            shifted = dt + timedelta(days=days)
            return shifted.strftime(fmt)
        except ValueError:
            continue
            
    # If it looks like a date but no format matches, try to extract year, month, day
    import re
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
                            shifted = dt + timedelta(days=days)
                            # Return in same format as input
                            return date_str.replace(match.group(0), 
                                f"{shifted.year if len(part) == 4 else shifted.year % 100:0{len(part)}d}"
                                f"{match.group(0)[len(match.group(1)):len(match.group(1))+1]}"
                                f"{shifted.month:0{len(match.group(2))}d}"
                                f"{match.group(0)[len(match.group(1))+len(match.group(2))+1:len(match.group(1))+len(match.group(2))+2]}"
                                f"{shifted.day:0{len(match.group(3))}d}")
                        except ValueError:
                            pass
                except ValueError:
                    pass
            
    # If no format matches, return a placeholder
    return "[REDACTED-DATE]"


