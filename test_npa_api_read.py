#!/usr/bin/env python3
"""
Test script to verify NPA API credentials and test read access.
"""
import os
import sys
import json
import httpx
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get credentials
username = os.getenv("NPA_API_USERNAME")
password = os.getenv("NPA_API_PASSWORD")
base_url = "https://npadsapi.dev.npauctions.com"

if not username or not password:
    print("❌ ERROR: NPA_API_USERNAME and NPA_API_PASSWORD must be set in .env")
    sys.exit(1)

print("=" * 60)
print("NPA API Credential Test")
print("=" * 60)
print(f"Username: {username}")
print(f"Password: {'*' * len(password)}")
print(f"Base URL: {base_url}")
print()

# Test 1: Try to create a minimal test lead (to verify write access)
print("Test 1: Testing Lead Creation (Write Access)")
print("-" * 60)

headers = {
    "accept": "application/json",
    "Content-Type": "application/json-patch+json"
}

# Minimal test lead data
test_lead = {
    "username": username,
    "password": password,
    "dataprovider": "IVR",
    "leadSource": "IVR-TEST",
    "firstName": "Test",
    "lastName": "User",
    "email": "test@powersportbuyers.com",
    "phone": "5555555555",
    "zipCode": "10001",
    "year": "2020",
    "make": "Yamaha",
    "model": "Test"
}

try:
    with httpx.Client(timeout=30) as client:
        url = f"{base_url}/api/Lead/LeadCreate"
        print(f"POST {url}")
        print(f"Payload: {json.dumps(test_lead, indent=2)}")
        print()

        r = client.post(url, json=test_lead, headers=headers)

        print(f"HTTP Status: {r.status_code}")
        print(f"Response: {json.dumps(r.json(), indent=2)}")
        print()

        response_data = r.json()
        if response_data.get("success"):
            print("✅ SUCCESS: Lead created successfully!")
            print(f"   Record ID: {response_data.get('recordID')}")
        else:
            error_msg = response_data.get("message", "Unknown error")
            print(f"❌ FAILED: {error_msg}")

except Exception as e:
    print(f"❌ ERROR: {e}")

print()
print("=" * 60)
print("Test Complete")
print("=" * 60)
