# deterministic_layer.py
"""
Deterministic preprocessing layer for Elara.
Handles wardrobe normalization, weather fetching, trend signals, and context pack generation.
All non-AI logic lives here to keep the LLM focused on choice and composition.
"""
from datetime import datetime
from typing import Dict, List
import hashlib
import json
import requests
from infra.cache import cache_get, cache_set
from contracts.models import WardrobeItem
import config

# Temperature bands in Celsius for weather-to-clothing mapping
TEMP_BANDS = [(10, "cold"), (18, "cool"), (24, "mild"), (100, "warm")]


def normalize_wardrobe(items: List[dict]) -> List[WardrobeItem]:
    """
    Normalizes raw wardrobe data into WardrobeItem models.
    - Maps free text to enums
    - Derives weather_suitability from fabrics and sleeve length
    - Consolidates tags with colors and fabrics
    """
    norm = []
    for raw in items:
        wi = WardrobeItem(**raw)
        if not wi.weather_suitability:
            wi.weather_suitability = derive_weather_suitability(wi)
        # Consolidate and deduplicate tags
        wi.tags = list(dict.fromkeys((wi.tags or []) + wi.colors + wi.fabrics))
        norm.append(wi)
    return norm


def derive_weather_suitability(wi: WardrobeItem) -> str:
    """
    Pure function to derive weather suitability from fabric and sleeve length.
    Returns: "cold", "cool", "mild", "mild to warm", or "warm"
    """
    fabrics = " ".join(wi.fabrics).lower()
    sleeve = (wi.sleeve_length or "").lower()

    if "wool" in fabrics or "down" in fabrics or "fleece" in fabrics:
        return "cold"
    if "linen" in fabrics or "crochet" in fabrics or sleeve in ["short", "sleeveless"]:
        return "mild to warm"
    if "cotton" in fabrics and sleeve == "short":
        return "warm"
    return "mild"


def fetch_weather(location_text: str, when_iso: str) -> dict:
    """
    Fetches weather data from OpenWeather API for a given location and datetime.
    Results are cached by (location, day, units) for 6 hours.

    Returns:
        dict with temp_c, precip_mm, wind_kph, humidity, conditions
    """
    key = f"wx:{location_text}:{when_iso[:10]}:{config.WEATHER_UNITS}"
    cached = cache_get(key)
    if cached:
        return cached

    # For MVP: use OpenWeather forecast API
    # In production, you'd geocode the location first
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "q": location_text,
        "appid": config.OPENWEATHER_API_KEY,
        "units": config.WEATHER_UNITS
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        # Find the forecast entry closest to the target datetime
        target = datetime.fromisoformat(when_iso)
        best = min(data["list"], key=lambda x: abs(datetime.fromtimestamp(x["dt"]) - target))

        wx = {
            "temp_c": best["main"]["temp"],
            "precip_mm": best.get("rain", {}).get("3h", 0) + best.get("snow", {}).get("3h", 0),
            "wind_kph": best["wind"]["speed"] * 3.6,
            "humidity": best["main"]["humidity"],
            "conditions": best["weather"][0]["main"]
        }

        cache_set(key, wx, ttl=6*3600)
        return wx

    except Exception as e:
        # Fallback to reasonable defaults if weather API fails
        return {
            "temp_c": 20,
            "precip_mm": 0,
            "wind_kph": 10,
            "humidity": 50,
            "conditions": "Clear"
        }


def derive_constraints(wx: dict) -> dict:
    """
    Derives clothing constraints from weather data.

    Returns:
        dict with temp_band, rain, outerwear_allowed, rain_safe_footwear
    """
    temp = wx["temp_c"]
    band = next(label for t, label in TEMP_BANDS if temp <= t)
    rain = wx["precip_mm"] > 0.2

    return {
        "temp_band": band,
        "rain": rain,
        "outerwear_allowed": band in ["cold", "cool"],
        "rain_safe_footwear": rain
    }


def load_trends() -> List[dict]:
    """
    Returns current fashion trend signals.
    In production, this would be updated weekly via a cron job.
    For MVP, returns a curated lightweight list.
    """
    return [
        {"tag": "linen", "w": 0.7},
        {"tag": "espresso-brown", "w": 0.4},
        {"tag": "chunky-loafers", "w": 0.5},
        {"tag": "relaxed-fit", "w": 0.6},
        {"tag": "neutral-tones", "w": 0.8}
    ]


def prepare_input(user_input: dict) -> dict:
    """
    Main entry point for the deterministic layer.
    Orchestrates all preprocessing and returns a clean ContextPack for the LLM.

    Args:
        user_input: Raw session input with user_profile, session, wardrobe, limits

    Returns:
        context_pack: Structured dict ready for LLM consumption with a content hash
    """
    # Fetch weather for the session
    wx = fetch_weather(
        user_input["session"]["location"],
        user_input["session"]["datetime_local_iso"]
    )

    # Build constraints object
    constraints = {
        "max_online_items_per_look": user_input.get("limits", {}).get(
            "max_online_items_per_look",
            config.MAX_ONLINE_ITEMS_PER_LOOK
        ),
        "retailers_allowlist": user_input.get("limits", {}).get(
            "retailers_allowlist",
            config.RETAILER_ALLOWLIST
        ),
        "budget": user_input["user_profile"].get("budget", {
            "currency": config.DEFAULT_CURRENCY,
            "hard_cap": 300
        })
    }

    # Normalize wardrobe items
    ward = normalize_wardrobe(user_input["wardrobe"])

    # Create compact wardrobe index (only essential fields for LLM)
    compact_wardrobe = [
        {
            "id": w.id,
            "category": w.category,
            "subcategory": w.subcategory,
            "tags": w.tags[:8],  # Limit tags to prevent token bloat
            "colors": w.colors[:3],
            "score": w.score,
            "image": w.image
        }
        for w in ward
    ]

    # Assemble context pack
    context_pack = {
        "session": user_input["session"],
        "user_profile": user_input["user_profile"],
        "weather_compact": wx,
        "derived": derive_constraints(wx),
        "constraints": constraints,
        "trend_tags": load_trends(),
        "wardrobe_index": compact_wardrobe
    }

    # Add content hash for caching and debugging
    context_pack["_hash"] = hashlib.sha256(
        json.dumps(context_pack, sort_keys=True).encode()
    ).hexdigest()

    return context_pack
