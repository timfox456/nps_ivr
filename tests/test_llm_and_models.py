from app.llm import normalize_fields
from app.models import missing_fields


def test_normalize_fields_year_extraction():
    fields = {"vehicle_year": "It's a 2018 model"}
    out = normalize_fields(fields)
    assert out["vehicle_year"] == "2018"


def test_missing_fields_order():
    state = {"first_name": "A", "last_name": "B"}
    miss = missing_fields(state)
    # Address should be next missing based on REQUIRED_FIELDS order
    assert miss[0] == "address"
