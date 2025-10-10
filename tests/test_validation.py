"""
Tests for validation utilities.
"""
import pytest
from app.validation import (
    normalize_transcribed_email,
    normalize_phone,
    validate_email,
    validate_phone,
    validate_and_normalize_field,
)


class TestNormalizeTranscribedEmail:
    """Tests for email transcription normalization."""

    def test_basic_at_and_dot(self):
        assert normalize_transcribed_email("tfox at yahoo dot com") == "tfox@yahoo.com"

    def test_multiple_dots(self):
        assert normalize_transcribed_email("john dot smith at gmail dot com") == "john.smith@gmail.com"

    def test_underscore(self):
        assert normalize_transcribed_email("user underscore name at domain dot org") == "user_name@domain.org"

    def test_dash(self):
        assert normalize_transcribed_email("first dash last at example dot com") == "first-last@example.com"

    def test_hyphen(self):
        assert normalize_transcribed_email("first hyphen last at example dot com") == "first-last@example.com"

    def test_mixed_patterns(self):
        assert normalize_transcribed_email("john dot doe underscore 123 at company dash name dot co dot uk") == "john.doe_123@company-name.co.uk"

    def test_already_formatted(self):
        assert normalize_transcribed_email("test@example.com") == "test@example.com"

    def test_case_insensitive(self):
        assert normalize_transcribed_email("TFox AT Yahoo DOT Com") == "tfox@yahoo.com"

    def test_extra_spaces(self):
        assert normalize_transcribed_email("  john  at  example  dot  com  ") == "john@example.com"

    def test_auto_correct_gmail(self):
        assert normalize_transcribed_email("tfox at gmail") == "tfox@gmail.com"

    def test_auto_correct_yahoo(self):
        assert normalize_transcribed_email("john at yahoo") == "john@yahoo.com"

    def test_auto_correct_hotmail(self):
        assert normalize_transcribed_email("user at hotmail") == "user@hotmail.com"

    def test_auto_correct_outlook(self):
        assert normalize_transcribed_email("test at outlook") == "test@outlook.com"

    def test_auto_correct_with_dots_in_local(self):
        assert normalize_transcribed_email("john dot smith at gmail") == "john.smith@gmail.com"

    def test_auto_correct_does_not_affect_complete_domains(self):
        assert normalize_transcribed_email("user at gmail dot com") == "user@gmail.com"

    def test_auto_correct_icloud(self):
        assert normalize_transcribed_email("user at icloud") == "user@icloud.com"

    def test_auto_correct_aol(self):
        assert normalize_transcribed_email("user at aol") == "user@aol.com"


class TestNormalizePhone:
    """Tests for phone number normalization."""

    def test_ten_digits_plain(self):
        assert normalize_phone("5551234567") == "(555) 123-4567"

    def test_with_dashes(self):
        assert normalize_phone("555-123-4567") == "(555) 123-4567"

    def test_with_parens_and_dash(self):
        assert normalize_phone("(555) 123-4567") == "(555) 123-4567"

    def test_with_country_code(self):
        assert normalize_phone("+1 (555) 123-4567") == "(555) 123-4567"

    def test_eleven_digits_with_one(self):
        assert normalize_phone("15551234567") == "(555) 123-4567"

    def test_with_spaces(self):
        assert normalize_phone("555 123 4567") == "(555) 123-4567"

    def test_with_dots(self):
        assert normalize_phone("555.123.4567") == "(555) 123-4567"

    def test_invalid_length_returns_original(self):
        result = normalize_phone("12345")
        assert result == "12345"

    def test_already_formatted(self):
        assert normalize_phone("(555) 123-4567") == "(555) 123-4567"


class TestValidateEmail:
    """Tests for email validation."""

    def test_valid_basic_email(self):
        is_valid, error = validate_email("test@example.com")
        assert is_valid is True
        assert error is None

    def test_valid_with_subdomain(self):
        is_valid, error = validate_email("user@mail.example.com")
        assert is_valid is True
        assert error is None

    def test_valid_with_plus(self):
        is_valid, error = validate_email("user+tag@example.com")
        assert is_valid is True
        assert error is None

    def test_valid_with_dots(self):
        is_valid, error = validate_email("first.last@example.com")
        assert is_valid is True
        assert error is None

    def test_valid_with_numbers(self):
        is_valid, error = validate_email("user123@example456.com")
        assert is_valid is True
        assert error is None

    def test_invalid_no_at(self):
        is_valid, error = validate_email("testexample.com")
        assert is_valid is False
        assert "'at' symbol" in error

    def test_invalid_multiple_at(self):
        is_valid, error = validate_email("test@@example.com")
        assert is_valid is False
        assert "'at' symbols" in error

    def test_invalid_no_domain(self):
        is_valid, error = validate_email("test@")
        assert is_valid is False
        assert "domain" in error.lower()

    def test_invalid_no_local(self):
        is_valid, error = validate_email("@example.com")
        assert is_valid is False
        assert "before the 'at'" in error

    def test_invalid_no_dot_in_domain(self):
        is_valid, error = validate_email("test@example")
        assert is_valid is False
        assert "dot" in error.lower()

    def test_invalid_empty(self):
        is_valid, error = validate_email("")
        assert is_valid is False
        assert "didn't catch" in error.lower() or "empty" in error.lower()

    def test_invalid_too_short(self):
        is_valid, error = validate_email("a@")
        assert is_valid is False

    def test_strips_whitespace(self):
        is_valid, error = validate_email("  test@example.com  ")
        assert is_valid is True
        assert error is None


class TestValidatePhone:
    """Tests for phone number validation."""

    def test_valid_ten_digits(self):
        is_valid, error = validate_phone("5552234567")
        assert is_valid is True
        assert error is None

    def test_valid_formatted(self):
        is_valid, error = validate_phone("(555) 223-4567")
        assert is_valid is True
        assert error is None

    def test_valid_with_dashes(self):
        is_valid, error = validate_phone("555-223-4567")
        assert is_valid is True
        assert error is None

    def test_valid_with_country_code(self):
        is_valid, error = validate_phone("+1 555-223-4567")
        assert is_valid is True
        assert error is None

    def test_valid_eleven_digits_with_one(self):
        is_valid, error = validate_phone("15552234567")
        assert is_valid is True
        assert error is None

    def test_invalid_too_short(self):
        is_valid, error = validate_phone("555123")
        assert is_valid is False
        assert "10 digits" in error

    def test_invalid_too_long(self):
        is_valid, error = validate_phone("555123456789")
        assert is_valid is False
        assert "10 digits" in error

    def test_invalid_area_code_starts_with_zero(self):
        is_valid, error = validate_phone("0551234567")
        assert is_valid is False
        assert "Area code" in error

    def test_invalid_area_code_starts_with_one(self):
        is_valid, error = validate_phone("1552234567")
        assert is_valid is False
        assert "Area code" in error

    def test_invalid_exchange_starts_with_zero(self):
        # Use non-555 area code since 555 numbers are exempt from exchange validation
        is_valid, error = validate_phone("4200234567")
        assert is_valid is False
        assert "Exchange" in error

    def test_invalid_exchange_starts_with_one(self):
        # Use non-555 area code since 555 numbers are exempt from exchange validation
        is_valid, error = validate_phone("4201234567")
        assert is_valid is False
        assert "Exchange" in error

    def test_invalid_all_same_digits(self):
        is_valid, error = validate_phone("5555555555")
        assert is_valid is False
        assert "all same digits" in error

    def test_invalid_empty(self):
        is_valid, error = validate_phone("")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_strips_whitespace(self):
        is_valid, error = validate_phone("  5552234567  ")
        assert is_valid is True
        assert error is None


class TestValidateAndNormalizeField:
    """Tests for the combined validate and normalize function."""

    def test_email_field_with_transcription(self):
        normalized, is_valid, error = validate_and_normalize_field("email", "tfox at yahoo dot com")
        assert normalized == "tfox@yahoo.com"
        assert is_valid is True
        assert error is None

    def test_email_field_invalid(self):
        normalized, is_valid, error = validate_and_normalize_field("email", "not-an-email")
        assert is_valid is False
        assert error is not None

    def test_phone_field_normalization(self):
        normalized, is_valid, error = validate_and_normalize_field("phone", "555-223-4567")
        assert normalized == "(555) 223-4567"
        assert is_valid is True
        assert error is None

    def test_phone_field_invalid(self):
        normalized, is_valid, error = validate_and_normalize_field("phone", "123")
        assert is_valid is False
        assert error is not None

    def test_other_field_no_validation(self):
        normalized, is_valid, error = validate_and_normalize_field("first_name", "John")
        assert normalized == "John"
        assert is_valid is True
        assert error is None

    def test_vehicle_year_no_validation(self):
        normalized, is_valid, error = validate_and_normalize_field("vehicle_year", "2020")
        assert normalized == "2020"
        assert is_valid is True
        assert error is None


class TestRealWorldScenarios:
    """Tests based on real-world usage scenarios."""

    def test_voice_email_various_formats(self):
        test_cases = [
            ("tfox at yahoo dot com", "tfox@yahoo.com"),
            ("john.smith at gmail dot com", "john.smith@gmail.com"),
            ("user underscore 123 at company dash mail dot org", "user_123@company-mail.org"),
            ("support at example dot co dot uk", "support@example.co.uk"),
        ]
        for input_text, expected in test_cases:
            normalized = normalize_transcribed_email(input_text)
            assert normalized == expected
            is_valid, error = validate_email(normalized)
            assert is_valid is True, f"Failed for {input_text}: {error}"

    def test_phone_various_formats(self):
        test_cases = [
            "5552234567",
            "(555) 223-4567",
            "555-223-4567",
            "+1 555 223 4567",
            "1-555-223-4567",
            "15552234567",
        ]
        for phone in test_cases:
            normalized = normalize_phone(phone)
            is_valid, error = validate_phone(normalized)
            assert is_valid is True, f"Failed for {phone}: {error}"
            assert normalized == "(555) 223-4567"

    def test_invalid_emails_caught(self):
        invalid_cases = [
            "notanemail",
            "missing@domain",
            "@nodomain.com",
            "double@@at.com",
            "no space@allowed.com",
            "",
        ]
        for email in invalid_cases:
            is_valid, error = validate_email(email)
            assert is_valid is False, f"Should be invalid: {email}"
            assert error is not None

    def test_invalid_phones_caught(self):
        invalid_cases = [
            "123",  # Too short
            "12345678901234",  # Too long
            "0001234567",  # Area code starts with 0
            "1111234567",  # Area code starts with 1
            "5555555555",  # All same digits
            "",  # Empty
        ]
        for phone in invalid_cases:
            is_valid, error = validate_phone(phone)
            assert is_valid is False, f"Should be invalid: {phone}"
            assert error is not None
