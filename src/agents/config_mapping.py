"""Mapping utilities for NL -> Scenario Config pipeline."""

from typing import Dict, Any, Optional, List
import re

# CityLearn climate zone mapping
# Maps weather/climate descriptions to CityLearn TMY3 climate zones
CLIMATE_ZONE_MAP = {
    # US Climate Zones (TMY3)
    "tmy3_722950": [
        "los angeles",
        "la",
        "southern california",
        "la county",
        "california coast",
        "mediterranean",
        "california climate",
        "zone 3",
    ],
    "tmy3_723810": ["san francisco", "sf", "bay area", "northern california coast"],
    "tmy3_724926": ["san diego", "sd", "southern california coast"],
    "tmy3_725030": [
        "phoenix",
        "arizona",
        "desert southwest",
        "phoenix",
        "arizona desert",
    ],
    "tmy3_722780": ["las vegas", "nevada", "mojave desert"],
    "tmy3_726813": [
        "houston",
        "texas",
        "gulf coast",
        "humid subtropical",
        "houston",
        "texas gulf",
    ],
    "tmy3_722499": ["denver", "colorado", "mountain west", "high plains"],
    "tmy3_725340": [
        "miami",
        "florida",
        "tropical",
        "subtropical",
        "madrid",
        "spain",
        "mediterranean",
        "rome",
        "italy",
        "mediterranean",
        "hot dry",
        "desert",
        "arid",
        "zone 2",
        "tropical",
        "humid subtropical",
        "zone 1",
    ],
    "tmy3_725090": ["houston", "texas gulf"],
    "tmy3_744860": [
        "new york",
        "nyc",
        "northeast",
        "humid continental",
        "cold",
        "continental",
        "zone 5",
    ],
    "tmy3_726580": ["dallas", "texas north"],
    "tmy3_745600": [
        "boston",
        "massachusetts",
        "new england",
        "london",
        "uk",
        "united kingdom",
        "marine west coast",
        "paris",
        "france",
        "western europe",
        "stockholm",
        "sweden",
        "scandinavia",
    ],
    "tmy3_745940": [
        "philadelphia",
        "pennsylvania",
        "mid-atlantic",
        "amsterdam",
        "netherlands",
    ],
    "tmy3_724050": [
        "seattle",
        "washington",
        "pacific northwest",
        "marine west coast",
        "marine",
        "coastal",
        "cool wet",
        "zone 4",
    ],
    "tmy3_727930": [
        "chicago",
        "illinois",
        "midwest",
        "continental",
        "cold",
        "continental",
        "zone 5",
    ],
    "tmy3_723170": ["atlanta", "georgia", "southeast", "atlanta", "georgia"],
    "tmy3_722150": [
        "honolulu",
        "hawaii",
        "tropical",
        "tropical",
        "humid subtropical",
        "zone 1",
    ],
    "tmy3_725830": ["san antonio", "texas central"],
    "tmy3_725820": ["austin", "texas central"],
    # Generic climate types merged above
}

# Reverse lookup for common names
CLIMATE_ZONE_ALIASES = {}
for zone, aliases in CLIMATE_ZONE_MAP.items():
    for alias in aliases:
        CLIMATE_ZONE_ALIASES[alias.lower()] = zone


def map_weather_to_climate_zone(weather_description: str) -> Optional[str]:
    """
    Map weather/climate description to CityLearn TMY3 climate zone.

    Args:
        weather_description: Natural language weather/climate description

    Returns:
        TMY3 climate zone identifier or None if no match
    """
    if not weather_description:
        return None

    desc_lower = weather_description.lower()

    # Direct alias match
    for alias, zone in CLIMATE_ZONE_ALIASES.items():
        if alias in desc_lower:
            return zone

    # Check zone keywords
    for zone, aliases in CLIMATE_ZONE_MAP.items():
        for alias in aliases:
            if alias in desc_lower:
                return zone

    return None


# pandapower network type mapping
PANDAPOWER_NETWORK_MAP = {
    "ieee_13": ["ieee 13", "13 bus", "small network", "test network"],
    "ieee_34": ["ieee 34", "34 bus", "medium network", "distribution"],
    "ieee_123": ["ieee 123", "123 bus", "large network"],
    "simbench": ["simbench", "simbench network", "german", "european"],
    "custom": ["custom", "custom network", "user defined"],
}


def map_grid_to_pandapower(grid_description: str) -> str:
    """
    Map grid description to pandapower network type.

    Args:
        grid_description: Natural language grid/network description

    Returns:
        pandapower network type identifier
    """
    if not grid_description:
        return "ieee_34"  # Default

    desc_lower = grid_description.lower()

    for network_type, aliases in PANDAPOWER_NETWORK_MAP.items():
        for alias in aliases:
            if alias in desc_lower:
                return network_type

    return "ieee_34"  # Default


# Building type mapping
BUILDING_TYPE_MAP = {
    "residential": [
        "residential",
        "home",
        "house",
        "apartment",
        "dwelling",
        "single family",
    ],
    "commercial": ["commercial", "office", "retail", "store", "mall", "shopping"],
    "industrial": ["industrial", "factory", "manufacturing", "warehouse", "plant"],
    "mixed": ["mixed", "mixed-use", "multi-use"],
}


def map_building_type(building_description: str) -> str:
    """Map building description to BuildingType."""
    if not building_description:
        return "residential"

    desc_lower = building_description.lower()

    for btype, aliases in BUILDING_TYPE_MAP.items():
        for alias in aliases:
            if alias in desc_lower:
                return btype

    return "residential"


# Tariff type mapping
TARIFF_TYPE_MAP = {
    "time_of_use": ["time of use", "tou", "tiered", "peak off-peak", "peak/off-peak"],
    "real_time": ["real time", "real-time", "rtp", "hourly pricing"],
    "flat": ["flat", "fixed rate", "constant", "single rate"],
    "demand": ["demand charge", "demand-based", "capacity charge"],
}


def map_tariff_type(tariff_description: str) -> str:
    """Map tariff description to tariff type."""
    if not tariff_description:
        return "time_of_use"

    desc_lower = tariff_description.lower()

    for ttype, aliases in TARIFF_TYPE_MAP.items():
        for alias in aliases:
            if alias in desc_lower:
                return ttype

    return "time_of_use"


# Market type mapping
MARKET_TYPE_MAP = {
    "uniform_price": ["uniform price", "uniform", "single price", "marginal price"],
    "weighted": ["weighted", "weighted average", "volume weighted"],
    "carbon_aware": ["carbon aware", "carbon-aware", "green", "emissions aware"],
    "fairness_aware": ["fairness", "fair", "equitable", "proportional"],
    "lmp": ["lmp", "locational marginal price", "locational marginal pricing"],
    "p2p": ["peer to peer", "p2p", "peer-to-peer", "direct trade"],
}


def map_market_type(market_description: str) -> str:
    """Map market description to market type."""
    if not market_description:
        return "uniform_price"

    desc_lower = market_description.lower()

    for mtype, aliases in MARKET_TYPE_MAP.items():
        for alias in aliases:
            if alias in desc_lower:
                return mtype

    return "uniform_price"


def extract_numeric_values(text: str, unit_keywords: List[str]) -> Dict[str, float]:
    """Extract numeric values with units from text."""
    values = {}

    for keyword in unit_keywords:
        # Pattern: number followed by keyword
        pattern = rf"(\d+(?:\.\d+)?)\s*(?:{keyword}|{keyword}s?)"
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            values[keyword] = float(matches[-1])  # Take last match

    return values


def parse_location(text: str) -> Dict[str, Any]:
    """Parse location from text."""
    location = {}

    # Simple regex for lat/lon
    lat_lon_pattern = r"(\d+(?:\.\d+)?)\s*[°,]\s*(-?\d+(?:\.\d+)?)\s*[°,]"
    matches = re.findall(lat_lon_pattern, text)
    if matches:
        location["lat"] = float(matches[0][0])
        location["lon"] = float(matches[0][1])

    # Try to extract city/state/country
    # This is simplified - in practice would use geocoding
    return location


def extract_asset_counts(text: str) -> Dict[str, int]:
    """Extract asset counts from text."""
    counts = {}

    # Pattern: number + asset type
    patterns = {
        "building_count": r"(\d+)\s*(?:building|home|house|dwelling)",
        "ev_count": r"(\d+)\s*(?:ev|electric vehicle|car)",
        "pv_count": r"(\d+)\s*(?:pv|solar|panel)",
        "battery_count": r"(\d+)\s*(?:battery|storage)",
    }

    for key, pattern in patterns.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            counts[key] = int(matches[-1])

    return counts
