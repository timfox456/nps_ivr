#!/usr/bin/env python3
"""
Test script for NPA API LeadCreate endpoint.
This script tests the create_lead function with sample data.
"""
import asyncio
import sys
from app.salesforce import create_lead
from app.config import settings

# Sample lead data based on the IVR collection
SAMPLE_LEAD = {
    "first_name": "John",
    "last_name": "Smith",
    "phone": "(555) 123-4567",
    "email": "john.smith@example.com",
    "address": "California",  # This is actually the STATE
    "zipcode": "90210",
    "vehicle_make": "Harley-Davidson",
    "vehicle_model": "Street Glide",
    "vehicle_year": "2020",
    "_channel": "voice",
}

async def test_lead_creation():
    """Test creating a lead via NPA API."""
    print("=" * 60)
    print("NPA API LeadCreate Test")
    print("=" * 60)
    print()

    # Check configuration
    print("Configuration Check:")
    print(f"  API Base URL: {settings.npa_api_base_url}")
    print(f"  API Username: {'✓ Set' if settings.npa_api_username else '✗ Not Set'}")
    print(f"  API Password: {'✓ Set' if settings.npa_api_password else '✗ Not Set'}")
    print(f"  Lead Source:  {settings.npa_lead_source}")
    print()

    if not settings.npa_api_username or not settings.npa_api_password:
        print("⚠️  WARNING: NPA API credentials not configured!")
        print("   Set NPA_API_USERNAME and NPA_API_PASSWORD in .env file")
        print("   The create_lead function will return None without credentials.")
        print()

    # Display sample data
    print("Sample Lead Data:")
    for key, value in SAMPLE_LEAD.items():
        if not key.startswith("_"):
            print(f"  {key:15s}: {value}")
    print()

    # Test the API call
    print("Attempting to create lead...")
    print()

    try:
        lead_id = await create_lead(SAMPLE_LEAD)

        if lead_id:
            print(f"✓ Success! Lead created with ID: {lead_id}")
            return 0
        else:
            print("⚠️  Lead creation returned None (likely due to missing credentials)")
            print("   This is expected if credentials are not configured.")
            return 1

    except Exception as e:
        print(f"✗ Error creating lead: {str(e)}")
        print()
        print("This could mean:")
        print("  1. Invalid credentials (check NPA_API_USERNAME and NPA_API_PASSWORD)")
        print("  2. API endpoint is incorrect")
        print("  3. Network connectivity issue")
        print("  4. API is temporarily unavailable")
        return 2

if __name__ == "__main__":
    exit_code = asyncio.run(test_lead_creation())
    sys.exit(exit_code)
