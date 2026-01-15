from typing import Dict, Any, Optional
import httpx
import logging
from .config import settings

logger = logging.getLogger(__name__)

async def get_session_token(username: str, password: str, base_url: str) -> Optional[str]:
    """
    Get a session token from the NPA API.

    Args:
        username: NPA API username
        password: NPA API password
        base_url: Base URL for the NPA API

    Returns:
        Session token if successful, None otherwise
    """
    # Try GET request with query parameters
    url = base_url.rstrip("/") + "/api/Account/Login"

    try:
        headers = {
            "accept": "application/json",
        }
        params = {
            "username": username,
            "password": password
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, params=params, headers=headers)
            r.raise_for_status()

            response_data = r.json()
            session_token = response_data.get("sessionToken")

            if session_token:
                logger.info("Successfully obtained NPA session token")
                return session_token
            else:
                logger.error(f"No session token in response: {response_data}")
                return None

    except Exception as e:
        logger.error(f"Failed to get session token: {str(e)}")
        return None


async def create_lead(payload: Dict[str, Any]) -> Optional[str]:
    """
    Create a lead in NPA system via LeadCreate API endpoint.
    Returns a lead ID string if successful, or None if not configured.

    Args:
        payload: Dictionary containing lead information with keys:
            Required fields collected by IVR:
            - full_name, phone, email
            - address (STATE only)
            - vehicle_make, vehicle_model, vehicle_year

            Optional fields with defaults:
            - zipcode (defaults to "00000" - not collected by IVR)
            - vin (defaults to "N/A")
            - miles_hours (defaults to "1")
            - asking_price (defaults to 1)
            - images (defaults to placeholder 1x1 PNG)
            - _channel (for tracking source: "sms" or "voice")

    Returns:
        Lead ID if successful, None if credentials not configured

    Raises:
        httpx.HTTPStatusError: If API call fails
    """
    username = settings.npa_api_username
    password = settings.npa_api_password

    if not username or not password:
        logger.warning("NPA API credentials not configured. Skipping lead creation.")
        return None

    # Construct the LeadCreate endpoint
    url = settings.npa_api_base_url.rstrip("/") + "/api/Lead/LeadCreate"

    # Split full_name into first and last name for API
    full_name = payload.get("full_name", "")
    name_parts = full_name.split(None, 1)  # Split on first whitespace
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    # Map our collected fields to NPA API format
    # Based on the Swagger API schema (camelCase field names)
    data = {
        "sessionToken": "",
        "dataProviderDealerToken": "",
        "username": username,
        "password": password,
        "email": payload.get("email", "noemail@placeholder.com"),  # Placeholder for voice calls without email
        "phone": payload.get("phone", ""),
        "firstName": first_name,
        "lastName": last_name,
        "zip": payload.get("zipcode", "00000"),  # Default placeholder - not collected by IVR
        "vin": payload.get("vin", "N/A"),  # Default to "N/A" if not provided
        "milesHours": payload.get("miles_hours", "1"),  # Default to "1" if not provided
        "askingPrice": int(payload.get("asking_price", 1)) if payload.get("asking_price") else 1,
        # Tiny 1x1 transparent PNG as base64 - valid placeholder image
        "images": payload.get("images", [{"url": "", "base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "name": "placeholder.png", "id": None, "data": "", "length": 68}]),
        "resizeImages": False,
        "year": int(payload.get("vehicle_year", 0)) if payload.get("vehicle_year") else 0,
        "make": payload.get("vehicle_make", ""),
        "model": payload.get("vehicle_model", ""),
        "lastStartDate": None,
        "state": payload.get("address", ""),  # Our 'address' field is actually STATE
        "isFinanced": False,
        "financedBankName": "",
        "financedAmount": 0,
        "refNumber": "",
        "gclid": "",
        "additionalNotes": f"Lead collected via {payload.get('_channel', 'IVR')}",
        "condition": "",
        "okToText": "true",  # Default to true since they're using SMS/voice
        "leadSource": settings.npa_lead_source
    }

    logger.info(f"Creating NPA lead for {full_name}")

    try:
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json-patch+json"
        }
        async with httpx.AsyncClient(timeout=30) as client:
            # Log request details for debugging (mask sensitive data)
            logger.info(f"NPA API Request - URL: {url}, Username: {username[:3]}***")
            logger.debug(f"NPA API Request payload: {data}")

            # Send the data directly (no wrapper needed)
            r = await client.post(url, json=data, headers=headers)

            # Log response status code
            logger.info(f"NPA API Response - Status: {r.status_code}")

            r.raise_for_status()

            # Parse response - structure may vary, log for debugging
            response_data = r.json()
            logger.info(f"NPA API response: {response_data}")

            # Check if the API call was successful
            success = response_data.get("success", False)
            message = response_data.get("message", "")
            record_id = response_data.get("recordID")

            if success and record_id:
                logger.info(f"Successfully created NPA lead: {record_id}")
                return str(record_id)
            elif not success:
                logger.error(f"NPA API rejected lead: {message}")
                logger.error(f"Full API response for debugging: {response_data}")

                # Create a clear error summary for reporting
                error_summary = {
                    "error_type": "NPA_API_REJECTION",
                    "http_status": r.status_code,
                    "api_success": success,
                    "error_message": message,
                    "api_version": response_data.get("apiInfo", {}).get("apiVersion"),
                    "app_version": response_data.get("apiInfo", {}).get("applicationVersion"),
                    "url": url,
                    "username": f"{username[:3]}***"
                }
                logger.error(f"ERROR REPORT - {error_summary}")
                raise Exception(f"NPA API error: {message}")
            else:
                logger.warning(f"Lead creation uncertain - no record ID: {response_data}")
                return None

    except httpx.HTTPStatusError as e:
        logger.error(f"NPA API HTTP error: Status {e.response.status_code}")
        logger.error(f"Response body: {e.response.text}")
        logger.error(f"Request URL: {e.request.url}")
        raise
    except Exception as e:
        logger.error(f"Failed to create NPA lead: {str(e)}")
        raise
