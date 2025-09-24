from typing import Dict, Any, Optional
import httpx
from .config import settings

async def create_lead(payload: Dict[str, Any]) -> Optional[str]:
    """
    Placeholder for creating a lead in Salesforce.
    Returns a lead ID string if successful, or None if not configured.
    """
    base = settings.salesforce_base_url
    token = settings.salesforce_api_token
    if not base or not token:
        return None

    url = base.rstrip("/") + "/leads"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Map fields if Salesforce requires specific keys
    data = {
        "FirstName": payload.get("first_name"),
        "LastName": payload.get("last_name"),
        "Phone": payload.get("phone"),
        "Email": payload.get("email"),
        "Street": payload.get("address"),
        "Company": "NPA Lead",
        "Description": f"Vehicle: {payload.get('vehicle_year','')} {payload.get('vehicle_make','')} {payload.get('vehicle_model','')}",
        "Custom_Vehicle_Make__c": payload.get("vehicle_make"),
        "Custom_Vehicle_Model__c": payload.get("vehicle_model"),
        "Custom_Vehicle_Year__c": payload.get("vehicle_year"),
    }

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, headers=headers, json=data)
        r.raise_for_status()
        obj = r.json()
        return obj.get("id") or obj.get("Id")
