#!/usr/bin/env python3
"""
Test script for email speech formatting with NATO phonetic alphabet.
"""
from app.main import format_email_for_speech

# Test cases
test_emails = [
    "tfox@yahoo.com",
    "john.smith@gmail.com",
    "info123@example.org",
    "kristineisabelb@gmail.com",
    "test_user@domain.co.uk",
    "a.b.c@test.com"
]

print("=" * 80)
print("Email Speech Formatting Test (NATO Phonetic Alphabet)")
print("=" * 80)
print()

for email in test_emails:
    normal, spelled = format_email_for_speech(email)
    print(f"Original Email: {email}")
    print(f"Normal Speech:  {normal}")
    print(f"Spelled Out:    {spelled}")
    print()
    print(f"Full Message: I heard your email is {normal}.")
    print(f"              [pause] {spelled}")
    print(f"              [pause] Is that correct?")
    print("-" * 80)
    print()

print("\nHow it sounds:")
print("1. Say it normally first: 'tfox at yahoo dot com'")
print("2. Then spell it out: 'that's T as in Tango, F as in Foxtrot...'")
print("3. Spelled part uses rate='slow' for clearer speech")
print("4. Pauses added before and after spelling")
