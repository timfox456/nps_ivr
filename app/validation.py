"""
Validation utilities for lead intake fields.
"""
import re
from datetime import datetime
from typing import Optional, Tuple


# Email validation regex (RFC 5322 simplified)
EMAIL_PATTERN = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)

# Phone validation - supports various formats
# Matches: (555) 123-4567, 555-123-4567, 5551234567, +1-555-123-4567, etc.
PHONE_PATTERN = re.compile(
    r'^\+?1?\s*\(?([0-9]{3})\)?[\s.-]?([0-9]{3})[\s.-]?([0-9]{4})$'
)


def normalize_transcribed_email(text: str) -> str:
    """
    Normalize voice-transcribed email addresses.

    Handles common transcription patterns:
    - "at" -> "@"
    - "dot" -> "."
    - "dash" or "hyphen" -> "-"
    - "underscore" -> "_"

    Also auto-corrects common domains:
    - "gmail" -> "gmail.com"
    - "yahoo" -> "yahoo.com"
    - "hotmail" -> "hotmail.com"
    - "outlook" -> "outlook.com"

    Examples:
        "tfox at yahoo dot com" -> "tfox@yahoo.com"
        "john dot smith at gmail dot com" -> "john.smith@gmail.com"
        "user underscore name at domain dot org" -> "user_name@domain.org"
        "tfox at yahoo" -> "tfox@yahoo.com"
        "john at gmail" -> "john@gmail.com"
    """
    text = text.lower().strip()

    # Replace common transcription patterns
    text = re.sub(r'\s+at\s+', '@', text)
    text = re.sub(r'\s+dot\s+', '.', text)
    text = re.sub(r'\s+(dash|hyphen)\s+', '-', text)
    text = re.sub(r'\s+underscore\s+', '_', text)

    # Remove any remaining spaces
    text = text.replace(' ', '')

    # Auto-correct common incomplete domains
    # Map of domain patterns to complete domains
    common_domains = {
        r'@gmail$': '@gmail.com',
        r'@yahoo$': '@yahoo.com',
        r'@hotmail$': '@hotmail.com',
        r'@outlook$': '@outlook.com',
        r'@icloud$': '@icloud.com',
        r'@aol$': '@aol.com',
        r'@protonmail$': '@protonmail.com',
        r'@msn$': '@msn.com',
    }

    for pattern, replacement in common_domains.items():
        text = re.sub(pattern, replacement, text)

    return text


def normalize_phone(text: str) -> str:
    """
    Normalize phone number to standard format.

    Extracts digits and formats as: (555) 123-4567
    If there are 11 digits starting with 1, strips the 1.

    Examples:
        "5551234567" -> "(555) 123-4567"
        "555-123-4567" -> "(555) 123-4567"
        "+1 (555) 123-4567" -> "(555) 123-4567"
        "15551234567" -> "(555) 123-4567"
    """
    # Extract all digits
    digits = re.sub(r'\D', '', text)

    # Strip leading 1 if we have 11 digits
    if len(digits) == 11 and digits[0] == '1':
        digits = digits[1:]

    # Format as (555) 123-4567 if we have 10 digits
    if len(digits) == 10:
        return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"

    # Return original if we can't normalize
    return text


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate email address format.

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if valid
        - (False, error_message) if invalid
    """
    if not email or not email.strip():
        return False, "I didn't catch your email address"

    email = email.strip()

    # Check length
    if len(email) > 254:
        return False, "that email address is too long"

    if len(email) < 3:
        return False, "that doesn't seem like a complete email address"

    # Check for @ symbol
    if '@' not in email:
        return False, "I didn't hear the 'at' symbol in your email address"

    # Check for multiple @ symbols
    if email.count('@') > 1:
        return False, "I heard multiple 'at' symbols in your email"

    # Split and validate parts
    if '@' in email:
        parts = email.split('@')
        if len(parts) != 2:
            return False, "I heard multiple 'at' symbols in your email"

        local, domain = parts

        if not local:
            return False, "I didn't hear the part before the 'at' symbol"

        if not domain:
            return False, "I didn't hear the domain after the 'at' symbol"

        if '.' not in domain:
            return False, "the email domain needs a 'dot' like 'gmail dot com'"

    # Check pattern
    if not EMAIL_PATTERN.match(email):
        return False, "that email format doesn't look right"

    return True, None


def validate_phone(phone: str) -> Tuple[bool, Optional[str]]:
    """
    Validate phone number format.

    Accepts US/Canada phone numbers in various formats.

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if valid
        - (False, error_message) if invalid
    """
    if not phone or not phone.strip():
        return False, "Phone number cannot be empty"

    phone = phone.strip()

    # Extract digits
    digits = re.sub(r'\D', '', phone)

    # Check if starts with 1 (country code)
    if len(digits) == 11:
        if digits[0] != '1':
            return False, "11-digit numbers must start with 1"
        digits = digits[1:]  # Strip country code

    # Must be exactly 10 digits
    if len(digits) != 10:
        return False, f"Phone number must be 10 digits (found {len(digits)}). Please provide a valid US phone number"

    # Check for invalid patterns (North American Numbering Plan rules)
    # Area code (NPA) - first digit cannot be 0 or 1
    if digits[0] == '0' or digits[0] == '1':
        return False, "Area code cannot start with 0 or 1"

    # Allow 555 area code (reserved for fictional/testing use)
    # For 555 numbers, skip exchange code validation since they're not real numbers
    is_555_number = digits[0:3] == '555'

    # Exchange code (NXX) - first digit cannot be 0 or 1 (except for 555 area codes)
    # Note: digits[3] is the first digit of the exchange code in format: (555) 123-4567
    #       Area code = digits[0:3] = 555
    #       Exchange = digits[3:6] = 123
    #       Line number = digits[6:10] = 4567
    if not is_555_number and (digits[3] == '0' or digits[3] == '1'):
        return False, "Exchange code cannot start with 0 or 1"

    # Check for obviously fake numbers
    if len(set(digits)) == 1:  # All same digit
        return False, "Phone number appears invalid (all same digits)"

    return True, None


def validate_vehicle_year(year: str) -> Tuple[bool, Optional[str]]:
    """
    Validate vehicle year.

    Accepts years from 1950 to current year + 1 (for next model year).

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if valid
        - (False, error_message) if invalid
    """
    if not year or not year.strip():
        return False, "I didn't catch the vehicle year"

    year_str = year.strip()

    # Try to parse as integer
    try:
        year_int = int(year_str)
    except ValueError:
        return False, "the vehicle year should be a number like 2020 or 1999"

    # Check if it's a valid 4-digit year
    if year_int < 1000 or year_int > 9999:
        return False, "the vehicle year should be a 4-digit year"

    # Get current year and next year (for next model year releases)
    current_year = datetime.now().year
    max_year = current_year + 1

    # Reasonable range: 1950 to next year
    if year_int < 1950:
        return False, f"the vehicle year seems too old. We typically handle vehicles from 1950 onwards"

    if year_int > max_year:
        return False, f"the vehicle year can't be later than {max_year}"

    return True, None


def validate_and_normalize_field(field_name: str, value: str) -> Tuple[str, bool, Optional[str]]:
    """
    Validate and normalize a field value.

    Args:
        field_name: Name of the field (e.g., 'email', 'phone')
        value: The value to validate

    Returns:
        Tuple of (normalized_value, is_valid, error_message)
    """
    value = str(value).strip()

    if field_name == "email":
        # Try to normalize transcribed email
        normalized = normalize_transcribed_email(value)
        is_valid, error = validate_email(normalized)
        return normalized, is_valid, error

    elif field_name == "phone":
        normalized = normalize_phone(value)
        is_valid, error = validate_phone(normalized)
        return normalized, is_valid, error

    elif field_name == "vehicle_year":
        is_valid, error = validate_vehicle_year(value)
        return value, is_valid, error

    # For other fields, just return as-is
    return value, True, None
