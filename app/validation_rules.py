"""
Business validation rules for lead qualification.

This module contains all business logic for determining if a lead is eligible.
All rules are deterministic and testable.
"""
from typing import Tuple, Optional


def categorize_rejection(rejection_message: str) -> str:
    """
    Categorize the rejection reason into a category for analytics.

    Returns one of: zip_code, vehicle_age, electric, slingshot, unknown
    """
    msg_lower = rejection_message.lower()

    if "alaska" in msg_lower or "hawaii" in msg_lower:
        return "zip_code"
    elif "electric" in msg_lower:
        return "electric"
    elif "slingshot" in msg_lower or "not interested" in msg_lower:
        return "slingshot"
    elif "cruiser" in msg_lower or "metric" in msg_lower or "side-by-side" in msg_lower or \
         "atv" in msg_lower or "dirt bike" in msg_lower or "scooter" in msg_lower:
        return "vehicle_age"
    else:
        return "unknown"


def validate_zip_code(zip_code: str) -> Tuple[bool, Optional[str]]:
    """
    Validate ZIP code meets service area requirements.

    Args:
        zip_code: 5-digit ZIP code string

    Returns:
        (is_valid, error_message)
        - is_valid: True if ZIP is eligible, False if rejected
        - error_message: None if valid, rejection reason if invalid
    """
    if not zip_code or len(zip_code) != 5 or not zip_code.isdigit():
        return False, "ZIP code must be exactly 5 digits"

    # Alaska ZIP codes: 995xx, 996xx, 997xx, 998xx, 999xx
    if zip_code.startswith(('995', '996', '997', '998', '999')):
        return False, "We don't currently service Alaska. We only service the continental United States."

    # Hawaii ZIP codes: 967xx, 968xx
    if zip_code.startswith(('967', '968')):
        return False, "We don't currently service Hawaii. We only service the continental United States."

    return True, None


def validate_vehicle_eligibility(
    year: int,
    make: str,
    model: str,
    vehicle_type: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate vehicle meets purchase criteria.

    Args:
        year: Vehicle year (4-digit)
        make: Vehicle manufacturer (e.g., "Yamaha", "Harley-Davidson")
        model: Vehicle model (e.g., "Grizzly", "Road King")
        vehicle_type: Optional vehicle category (e.g., "atv", "dirt_bike", "cruiser")

    Returns:
        (is_eligible, rejection_message)
        - is_eligible: True if we purchase this vehicle, False if rejected
        - rejection_message: None if eligible, reason if rejected
    """
    make_lower = make.lower() if make else ""
    model_lower = model.lower() if model else ""
    vehicle_type_lower = vehicle_type.lower() if vehicle_type else ""

    # Rule 1: Electric motorcycles - ALL years rejected
    electric_brands = ['zero', 'livewire', 'live wire']
    if any(brand in make_lower for brand in electric_brands) or any(brand in model_lower for brand in electric_brands):
        return False, "We don't currently purchase electric motorcycles."

    # Rule 2: Slingshot - ALL years rejected
    if 'slingshot' in model_lower or 'slingshot' in make_lower:
        return False, "We are not interested in that unit."

    # Rule 3: Domestic cruisers - 1999 and older
    domestic_cruiser_brands = ['harley', 'harley-davidson', 'indian', 'victory']
    is_domestic_cruiser = any(brand in make_lower for brand in domestic_cruiser_brands)
    is_cruiser_type = vehicle_type_lower in ['cruiser', 'domestic_cruiser']

    if (is_domestic_cruiser or is_cruiser_type) and year <= 1999:
        return False, f"We don't currently purchase domestic cruisers from {year} and older."

    # Rule 4: Metric motorcycles (sport bikes, standard bikes) - 2005 and older
    metric_brands = ['honda', 'yamaha', 'kawasaki', 'suzuki', 'ducati', 'bmw', 'triumph', 'ktm']
    metric_models = ['cbr', 'r1', 'r6', 'ninja', 'gsxr', 'gsx-r']
    is_metric = any(brand in make_lower for brand in metric_brands)
    is_sport_model = any(model_part in model_lower for model_part in metric_models)
    is_metric_type = vehicle_type_lower in ['sport_bike', 'metric', 'standard', 'sportbike']

    if (is_metric or is_sport_model or is_metric_type) and year <= 2005:
        # Only reject if it's clearly a metric motorcycle (not ATV/side-by-side from same brands)
        if vehicle_type_lower not in ['atv', 'side_by_side', 'utv', 'dirt_bike']:
            return False, f"We don't currently purchase metric motorcycles from {year} and older."

    # Rule 5: Side-by-side / UTV - 2009 and older
    side_by_side_keywords = ['rzr', 'maverick', 'rhino', 'teryx', 'ranger', 'mule', 'gator']
    is_side_by_side = any(keyword in model_lower for keyword in side_by_side_keywords)
    is_sxs_type = vehicle_type_lower in ['side_by_side', 'sxs', 'utv', 'side-by-side']

    if (is_side_by_side or is_sxs_type) and year <= 2009:
        return False, f"We don't currently purchase side-by-sides from {year} and older."

    # Rule 6: ATV - 2015 and older
    atv_keywords = ['rancher', 'grizzly', 'sportsman', 'outlander', 'kodiak', 'foreman', 'rubicon']
    is_atv = any(keyword in model_lower for keyword in atv_keywords)
    is_atv_type = vehicle_type_lower in ['atv', 'quad', 'four_wheeler']

    if (is_atv or is_atv_type) and year <= 2015:
        return False, f"We don't currently purchase ATVs from {year} and older."

    # Rule 7: Dirt bike / MX - 2015 and older
    dirt_bike_keywords = ['crf', 'yz', 'kx', 'rm', 'sx', 'exc', 'xc', 'mx']
    is_dirt_bike = any(keyword in model_lower for keyword in dirt_bike_keywords)
    is_dirt_type = vehicle_type_lower in ['dirt_bike', 'mx', 'motocross', 'dirtbike', 'enduro']

    if (is_dirt_bike or is_dirt_type) and year <= 2015:
        return False, f"We don't currently purchase dirt bikes from {year} and older."

    # Rule 8: Scooter - 2015 and older
    scooter_keywords = ['metropolitan', 'zuma', 'vespa', 'ruckus', 'scoopy', 'pcx']
    is_scooter = any(keyword in model_lower for keyword in scooter_keywords)
    is_scooter_type = vehicle_type_lower in ['scooter', 'moped']

    if (is_scooter or is_scooter_type) and year <= 2015:
        return False, f"We don't currently purchase scooters from {year} and older."

    # All checks passed - vehicle is eligible
    return True, None


def categorize_vehicle_type(make: str, model: str) -> str:
    """
    Attempt to categorize vehicle type from make and model.
    This is a helper for when LLM doesn't provide vehicle_type.

    Returns one of: atv, side_by_side, dirt_bike, scooter, cruiser, sport_bike, unknown
    """
    make_lower = make.lower() if make else ""
    model_lower = model.lower() if model else ""

    # Check for specific keywords
    if any(k in model_lower for k in ['rzr', 'maverick', 'rhino', 'teryx', 'ranger', 'mule', 'gator']):
        return 'side_by_side'

    if any(k in model_lower for k in ['grizzly', 'rancher', 'sportsman', 'outlander', 'kodiak', 'foreman']):
        return 'atv'

    if any(k in model_lower for k in ['crf', 'yz', 'kx', 'rm', 'sx', 'exc']):
        return 'dirt_bike'

    if any(k in model_lower for k in ['metropolitan', 'zuma', 'ruckus']):
        return 'scooter'

    if any(k in make_lower for k in ['vespa']):
        return 'scooter'

    if 'slingshot' in model_lower:
        return 'slingshot'

    # Check make for domestic cruisers
    if any(k in make_lower for k in ['harley', 'indian', 'victory']):
        return 'cruiser'

    # Check for sport bike models
    if any(k in model_lower for k in ['cbr', 'r1', 'r6', 'ninja', 'gsxr']):
        return 'sport_bike'

    return 'unknown'
