"""
Unit tests for business validation rules.
"""
import pytest
from app.validation_rules import validate_zip_code, validate_vehicle_eligibility, categorize_vehicle_type


class TestZipCodeValidation:
    """Test ZIP code validation rules"""

    def test_valid_zip_codes(self):
        """Valid ZIP codes should pass"""
        assert validate_zip_code("30093") == (True, None)
        assert validate_zip_code("90210") == (True, None)
        assert validate_zip_code("12345") == (True, None)

    def test_alaska_zip_codes(self):
        """Alaska ZIP codes should be rejected"""
        is_valid, message = validate_zip_code("99501")  # Anchorage
        assert is_valid is False
        assert "Alaska" in message

        assert validate_zip_code("99654")[0] is False  # 996xx
        assert validate_zip_code("99701")[0] is False  # 997xx
        assert validate_zip_code("99801")[0] is False  # 998xx
        assert validate_zip_code("99901")[0] is False  # 999xx

    def test_hawaii_zip_codes(self):
        """Hawaii ZIP codes should be rejected"""
        is_valid, message = validate_zip_code("96801")  # Honolulu
        assert is_valid is False
        assert "Hawaii" in message

        assert validate_zip_code("96720")[0] is False  # 967xx
        assert validate_zip_code("96850")[0] is False  # 968xx

    def test_invalid_format(self):
        """Invalid ZIP code formats should be rejected"""
        assert validate_zip_code("")[0] is False
        assert validate_zip_code("1234")[0] is False  # Too short
        assert validate_zip_code("123456")[0] is False  # Too long
        assert validate_zip_code("abcde")[0] is False  # Not digits


class TestVehicleEligibility:
    """Test vehicle eligibility rules"""

    def test_electric_motorcycles_rejected(self):
        """All electric motorcycles should be rejected"""
        is_eligible, msg = validate_vehicle_eligibility(2023, "Zero", "SR/F")
        assert is_eligible is False
        assert "electric" in msg.lower()

        is_eligible, msg = validate_vehicle_eligibility(2020, "LiveWire", "One")
        assert is_eligible is False
        assert "electric" in msg.lower()

    def test_slingshot_rejected(self):
        """Polaris Slingshot should be rejected"""
        is_eligible, msg = validate_vehicle_eligibility(2020, "Polaris", "Slingshot")
        assert is_eligible is False
        assert "not interested" in msg.lower()

    def test_domestic_cruiser_old_rejected(self):
        """Domestic cruisers 1999 and older should be rejected"""
        is_eligible, msg = validate_vehicle_eligibility(1999, "Harley-Davidson", "Road King")
        assert is_eligible is False
        assert "cruiser" in msg.lower()

        assert validate_vehicle_eligibility(1995, "Indian", "Chief")[0] is False
        assert validate_vehicle_eligibility(1990, "Victory", "Vegas")[0] is False

    def test_domestic_cruiser_new_accepted(self):
        """Domestic cruisers 2000 and newer should be accepted"""
        assert validate_vehicle_eligibility(2000, "Harley-Davidson", "Road King")[0] is True
        assert validate_vehicle_eligibility(2020, "Indian", "Chief")[0] is True

    def test_metric_motorcycle_old_rejected(self):
        """Metric motorcycles 2005 and older should be rejected"""
        is_eligible, msg = validate_vehicle_eligibility(2005, "Honda", "CBR600RR", "sport_bike")
        assert is_eligible is False
        assert "metric" in msg.lower()

        assert validate_vehicle_eligibility(2000, "Yamaha", "R1", "sport_bike")[0] is False
        assert validate_vehicle_eligibility(2003, "Kawasaki", "Ninja", "sport_bike")[0] is False

    def test_metric_motorcycle_new_accepted(self):
        """Metric motorcycles 2006 and newer should be accepted"""
        assert validate_vehicle_eligibility(2006, "Honda", "CBR600RR", "sport_bike")[0] is True
        assert validate_vehicle_eligibility(2020, "Yamaha", "R1", "sport_bike")[0] is True

    def test_side_by_side_old_rejected(self):
        """Side-by-sides 2009 and older should be rejected"""
        is_eligible, msg = validate_vehicle_eligibility(2009, "Polaris", "RZR", "side_by_side")
        assert is_eligible is False
        assert "side-by-side" in msg.lower()

        assert validate_vehicle_eligibility(2005, "Can-Am", "Maverick", "side_by_side")[0] is False
        assert validate_vehicle_eligibility(2008, "Yamaha", "Rhino", "side_by_side")[0] is False

    def test_side_by_side_new_accepted(self):
        """Side-by-sides 2010 and newer should be accepted"""
        assert validate_vehicle_eligibility(2010, "Polaris", "RZR", "side_by_side")[0] is True
        assert validate_vehicle_eligibility(2020, "Can-Am", "Maverick", "side_by_side")[0] is True

    def test_atv_old_rejected(self):
        """ATVs 2015 and older should be rejected"""
        is_eligible, msg = validate_vehicle_eligibility(2015, "Yamaha", "Grizzly", "atv")
        assert is_eligible is False
        assert "ATV" in msg

        assert validate_vehicle_eligibility(2010, "Honda", "Rancher", "atv")[0] is False
        assert validate_vehicle_eligibility(2014, "Polaris", "Sportsman", "atv")[0] is False

    def test_atv_new_accepted(self):
        """ATVs 2016 and newer should be accepted"""
        assert validate_vehicle_eligibility(2016, "Yamaha", "Grizzly", "atv")[0] is True
        assert validate_vehicle_eligibility(2020, "Honda", "Rancher", "atv")[0] is True

    def test_dirt_bike_old_rejected(self):
        """Dirt bikes 2015 and older should be rejected"""
        is_eligible, msg = validate_vehicle_eligibility(2015, "Honda", "CRF450R", "dirt_bike")
        assert is_eligible is False
        assert "dirt bike" in msg.lower()

        assert validate_vehicle_eligibility(2010, "Yamaha", "YZ250", "dirt_bike")[0] is False
        assert validate_vehicle_eligibility(2014, "Kawasaki", "KX450F", "dirt_bike")[0] is False

    def test_dirt_bike_new_accepted(self):
        """Dirt bikes 2016 and newer should be accepted"""
        assert validate_vehicle_eligibility(2016, "Honda", "CRF450R", "dirt_bike")[0] is True
        assert validate_vehicle_eligibility(2020, "Yamaha", "YZ250", "dirt_bike")[0] is True

    def test_scooter_old_rejected(self):
        """Scooters 2015 and older should be rejected"""
        is_eligible, msg = validate_vehicle_eligibility(2015, "Honda", "Metropolitan", "scooter")
        assert is_eligible is False
        assert "scooter" in msg.lower()

        assert validate_vehicle_eligibility(2010, "Yamaha", "Zuma", "scooter")[0] is False
        assert validate_vehicle_eligibility(2014, "Vespa", "Primavera", "scooter")[0] is False

    def test_scooter_new_accepted(self):
        """Scooters 2016 and newer should be accepted"""
        assert validate_vehicle_eligibility(2016, "Honda", "Metropolitan", "scooter")[0] is True
        assert validate_vehicle_eligibility(2020, "Yamaha", "Zuma", "scooter")[0] is True


class TestVehicleCategorization:
    """Test vehicle type categorization helper"""

    def test_categorize_atv(self):
        assert categorize_vehicle_type("Yamaha", "Grizzly 700") == "atv"
        assert categorize_vehicle_type("Honda", "Rancher") == "atv"
        assert categorize_vehicle_type("Polaris", "Sportsman") == "atv"

    def test_categorize_side_by_side(self):
        assert categorize_vehicle_type("Polaris", "RZR XP 1000") == "side_by_side"
        assert categorize_vehicle_type("Can-Am", "Maverick X3") == "side_by_side"
        assert categorize_vehicle_type("Yamaha", "Rhino") == "side_by_side"

    def test_categorize_dirt_bike(self):
        assert categorize_vehicle_type("Honda", "CRF450R") == "dirt_bike"
        assert categorize_vehicle_type("Yamaha", "YZ250") == "dirt_bike"
        assert categorize_vehicle_type("KTM", "450 SX-F") == "dirt_bike"

    def test_categorize_cruiser(self):
        assert categorize_vehicle_type("Harley-Davidson", "Road King") == "cruiser"
        assert categorize_vehicle_type("Indian", "Chief") == "cruiser"
        assert categorize_vehicle_type("Victory", "Vegas") == "cruiser"

    def test_categorize_sport_bike(self):
        assert categorize_vehicle_type("Honda", "CBR600RR") == "sport_bike"
        assert categorize_vehicle_type("Yamaha", "R1") == "sport_bike"
        assert categorize_vehicle_type("Kawasaki", "Ninja 650") == "sport_bike"

    def test_categorize_scooter(self):
        assert categorize_vehicle_type("Honda", "Metropolitan") == "scooter"
        assert categorize_vehicle_type("Yamaha", "Zuma") == "scooter"
        assert categorize_vehicle_type("Vespa", "Primavera") == "scooter"

    def test_categorize_slingshot(self):
        assert categorize_vehicle_type("Polaris", "Slingshot") == "slingshot"

    def test_categorize_unknown(self):
        """Unknown vehicles should return 'unknown'"""
        assert categorize_vehicle_type("Ferrari", "F40") == "unknown"
        assert categorize_vehicle_type("Toyota", "Camry") == "unknown"
        assert categorize_vehicle_type("Unknown", "Unknown") == "unknown"


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_metric_brand_atvs_accepted(self):
        """Metric brands (Honda/Yamaha) should be accepted as ATVs even if old"""
        # 2005 and older metric motorcycles are rejected, but ATVs should be accepted
        # if they're newer than 2015 (ATV cutoff)
        assert validate_vehicle_eligibility(2016, "Honda", "Rancher", "atv")[0] is True
        assert validate_vehicle_eligibility(2017, "Yamaha", "Grizzly", "atv")[0] is True

        # But old ATVs should still be rejected (2015 and older)
        assert validate_vehicle_eligibility(2015, "Honda", "Rancher", "atv")[0] is False
        assert validate_vehicle_eligibility(2010, "Yamaha", "Grizzly", "atv")[0] is False

    def test_metric_brand_side_by_sides_accepted(self):
        """Metric brands should be accepted as side-by-sides even if old motorcycle year"""
        # 2005 and older metric motorcycles are rejected, but side-by-sides should use
        # the side-by-side cutoff (2009)
        assert validate_vehicle_eligibility(2010, "Yamaha", "Rhino", "side_by_side")[0] is True
        assert validate_vehicle_eligibility(2011, "Honda", "Pioneer", "side_by_side")[0] is True

        # But old side-by-sides should still be rejected (2009 and older)
        assert validate_vehicle_eligibility(2009, "Yamaha", "Rhino", "side_by_side")[0] is False
        assert validate_vehicle_eligibility(2005, "Honda", "Pioneer", "side_by_side")[0] is False

    def test_case_insensitivity(self):
        """Make and model matching should be case-insensitive"""
        # Uppercase
        assert validate_vehicle_eligibility(2023, "ZERO", "SR/F")[0] is False
        assert validate_vehicle_eligibility(2020, "HARLEY-DAVIDSON", "ROAD KING")[0] is True

        # Mixed case
        assert validate_vehicle_eligibility(2023, "ZeRo", "SR/F")[0] is False
        assert validate_vehicle_eligibility(1999, "HaRlEy-DaViDsOn", "Road King")[0] is False

    def test_livewire_variants(self):
        """Test both 'LiveWire' and 'Live Wire' spellings"""
        assert validate_vehicle_eligibility(2020, "LiveWire", "One")[0] is False
        assert validate_vehicle_eligibility(2020, "Live Wire", "One")[0] is False
        assert validate_vehicle_eligibility(2023, "Harley-Davidson", "LiveWire")[0] is False

    def test_empty_strings(self):
        """Empty make/model should not crash"""
        # Should handle gracefully and return True (no rules triggered)
        assert validate_vehicle_eligibility(2020, "", "", "")[0] is True
        assert validate_vehicle_eligibility(2020, "", "Model", "")[0] is True
        assert validate_vehicle_eligibility(2020, "Make", "", "")[0] is True

    def test_zip_with_leading_zeros(self):
        """ZIP codes with leading zeros should work"""
        assert validate_zip_code("00501")[0] is True  # Puerto Rico (if we service it)
        assert validate_zip_code("01234")[0] is True  # Massachusetts
        assert validate_zip_code("09876")[0] is True  # New Jersey

    def test_boundary_years(self):
        """Test years just before and after cutoffs"""
        # Domestic cruiser: 1999 reject, 2000 accept
        assert validate_vehicle_eligibility(1998, "Harley-Davidson", "Road King")[0] is False
        assert validate_vehicle_eligibility(2001, "Harley-Davidson", "Road King")[0] is True

        # Metric: 2005 reject, 2006 accept
        assert validate_vehicle_eligibility(2004, "Honda", "CBR600RR", "sport_bike")[0] is False
        assert validate_vehicle_eligibility(2007, "Honda", "CBR600RR", "sport_bike")[0] is True

        # Side-by-side: 2009 reject, 2010 accept
        assert validate_vehicle_eligibility(2008, "Polaris", "RZR", "side_by_side")[0] is False
        assert validate_vehicle_eligibility(2011, "Polaris", "RZR", "side_by_side")[0] is True

        # ATV: 2015 reject, 2016 accept
        assert validate_vehicle_eligibility(2014, "Yamaha", "Grizzly", "atv")[0] is False
        assert validate_vehicle_eligibility(2017, "Yamaha", "Grizzly", "atv")[0] is True

    def test_slingshot_in_make_or_model(self):
        """Slingshot should be rejected whether in make or model"""
        assert validate_vehicle_eligibility(2020, "Polaris", "Slingshot")[0] is False
        assert validate_vehicle_eligibility(2020, "Slingshot", "R")[0] is False

    def test_vehicle_type_aliases(self):
        """Test various vehicle_type aliases"""
        # Side-by-side aliases
        assert validate_vehicle_eligibility(2009, "Polaris", "RZR", "sxs")[0] is False
        assert validate_vehicle_eligibility(2009, "Polaris", "RZR", "utv")[0] is False
        assert validate_vehicle_eligibility(2009, "Polaris", "RZR", "side-by-side")[0] is False

        # ATV aliases
        assert validate_vehicle_eligibility(2015, "Honda", "Rancher", "quad")[0] is False
        assert validate_vehicle_eligibility(2015, "Honda", "Rancher", "four_wheeler")[0] is False

        # Dirt bike aliases
        assert validate_vehicle_eligibility(2015, "Honda", "CRF450R", "mx")[0] is False
        assert validate_vehicle_eligibility(2015, "Honda", "CRF450R", "motocross")[0] is False
        assert validate_vehicle_eligibility(2015, "Honda", "CRF450R", "dirtbike")[0] is False
        assert validate_vehicle_eligibility(2015, "Honda", "CRF450R", "enduro")[0] is False

        # Scooter aliases
        assert validate_vehicle_eligibility(2015, "Honda", "Metropolitan", "moped")[0] is False

        # Sport bike aliases
        assert validate_vehicle_eligibility(2005, "Honda", "CBR600RR", "sportbike")[0] is False
