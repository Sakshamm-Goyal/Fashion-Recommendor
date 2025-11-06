# scoring_matrix.py
"""
Deterministic scoring system for outfit recommendations.
Implements the weighted scoring matrix from the PRD.
"""
import json
from typing import Dict, List

# Scoring weights (must sum to 1.0)
WEIGHTS = {
    "weather": 0.20,
    "occasion": 0.25,
    "color": 0.20,
    "fit_body": 0.20,
    "brand_budget": 0.10,
    "trend": 0.05
}


def clamp(x: float) -> float:
    """Clamps a value between 0 and 10."""
    return max(0, min(10, x))


def json_text(obj) -> str:
    """Converts object to lowercase JSON string for text matching."""
    # Handle Decimal types (from database) and Pydantic models
    def default_serializer(obj):
        from decimal import Decimal
        from pydantic import BaseModel

        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, BaseModel):
            # Convert Pydantic model to dict
            return obj.model_dump()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    return json.dumps(obj, ensure_ascii=False, default=default_serializer).lower()


def score_weather(outfit: dict, wx: dict, derived: dict) -> float:
    """
    Scores weather appropriateness (0-10).

    Considers:
    - Temperature band and fabric choices
    - Rain conditions and footwear
    - Layering appropriateness
    """
    band = derived["temp_band"]
    txt = json_text(outfit)
    s = 7.0  # baseline

    # Positive adjustments
    if band in ["warm", "mild"] and any(kw in txt for kw in ["linen", "cotton", "light"]):
        s += 1.5
    if band in ["cold", "cool"] and any(kw in txt for kw in ["wool", "knit", "layer", "jacket"]):
        s += 1.5

    # Negative adjustments
    if derived["rain"] and any(kw in txt for kw in ["suede", "canvas sneakers"]):
        s -= 2.0
    if band == "warm" and any(kw in txt for kw in ["wool", "heavy", "thick"]):
        s -= 1.5

    return clamp(s)


def score_occasion(outfit: dict, occasion: str, vibe: str) -> float:
    """
    Scores occasion appropriateness (0-10).

    Maps occasion types to expected garments and formality levels.
    """
    txt = json_text(outfit)
    occasion_lower = occasion.lower()
    vibe_lower = vibe.lower()

    s = 7.0  # baseline

    # Wedding scoring
    if "wedding" in occasion_lower:
        if any(kw in txt for kw in ["blazer", "dress shirt", "loafers", "oxford", "chinos"]):
            s += 2.0
        if "chill" in vibe_lower or "casual" in vibe_lower:
            if any(kw in txt for kw in ["linen", "light", "summer"]):
                s += 1.0
        if any(kw in txt for kw in ["t-shirt", "shorts", "flip-flops"]):
            s -= 2.0

    # Work/Business scoring
    elif "work" in occasion_lower or "business" in occasion_lower:
        if any(kw in txt for kw in ["blazer", "dress shirt", "trousers", "oxford", "loafers"]):
            s += 2.0
        if any(kw in txt for kw in ["jeans", "sneakers", "t-shirt"]):
            s -= 1.5

    # Casual/Date scoring
    elif any(kw in occasion_lower for kw in ["casual", "date", "dinner"]):
        if any(kw in txt for kw in ["jeans", "chinos", "polo", "shirt", "sneakers", "loafers"]):
            s += 1.5
        if "formal" in vibe_lower:
            if any(kw in txt for kw in ["blazer", "dress shirt"]):
                s += 1.0

    return clamp(s)


def score_color(outfit: dict, user_profile: dict) -> float:
    """
    Scores color compatibility (0-10).

    Considers:
    - Skin tone complementary colors
    - User color preferences
    """
    skin = (user_profile.get("skin_tone", "") or "").lower()
    prefs = [c.lower() for c in user_profile.get("color_prefs", [])]
    txt = json_text(outfit)[:300]  # limit search space

    s = 7.0  # baseline

    # Preference matches
    pref_matches = sum(1 for p in prefs if p in txt)
    s += min(2.0, pref_matches * 0.8)

    # Skin tone complementary colors
    if skin in ["olive", "medium"]:
        if any(kw in txt for kw in ["beige", "brown", "olive", "off-white", "cream", "earth"]):
            s += 1.0
        if any(kw in txt for kw in ["neon", "bright pink"]):
            s -= 0.5

    elif skin in ["fair", "light"]:
        if any(kw in txt for kw in ["navy", "charcoal", "burgundy", "forest green"]):
            s += 1.0

    elif skin in ["deep", "dark"]:
        if any(kw in txt for kw in ["white", "cream", "pastels", "bright colors"]):
            s += 1.0

    return clamp(s)


def score_fit_body(outfit: dict, user_profile: dict) -> float:
    """
    Scores fit and body type compatibility (0-10).

    Matches silhouettes to body types and fit preferences.
    """
    fit = (user_profile.get("fit_pref", "") or "").lower()
    body_type = (user_profile.get("body_type", "") or "").lower()
    txt = json_text(outfit)

    s = 7.0  # baseline

    # Fit preference matches
    if fit and fit in txt:
        s += 1.5

    # Body type specific adjustments
    if "athletic" in body_type:
        if any(kw in txt for kw in ["slim", "tapered", "fitted"]):
            s += 1.0
        if "oversized" in txt and "oversized" in txt:  # double oversized
            s -= 1.0

    elif "slim" in body_type:
        if any(kw in txt for kw in ["slim", "fitted", "tailored"]):
            s += 1.0

    elif any(kw in body_type for kw in ["plus", "curvy"]):
        if any(kw in txt for kw in ["relaxed", "comfort", "stretch"]):
            s += 1.0

    return clamp(s)


def score_brand_budget(outfit_items: List[dict], brand_prefs: List[str], budget: dict) -> float:
    """
    Scores brand and budget alignment (0-10).

    Considers:
    - Presence of preferred brands
    - Total cost vs budget constraints
    """
    s = 7.0  # baseline

    # Brand preference matches
    item_sources = " ".join([i.get("source", "").lower() for i in outfit_items])
    brand_matches = sum(1 for b in brand_prefs if b.lower() in item_sources)
    s += min(2.0, brand_matches * 0.7)

    # Budget compliance
    total_cost = sum(
        i.get("price", {}).get("value", 0)
        for i in outfit_items
        if isinstance(i.get("price"), dict)
    )

    hard_cap = budget.get("hard_cap", 300)
    soft_cap = budget.get("soft_cap", 150)

    if total_cost > hard_cap:
        s -= 3.0  # major penalty for exceeding hard budget
    elif total_cost > soft_cap:
        s -= 1.0  # minor penalty for exceeding soft budget
    elif total_cost <= soft_cap * 0.7:
        s += 1.0  # bonus for being well under budget

    return clamp(s)


def score_trend(outfit: dict, trend_tags: List[dict]) -> float:
    """
    Scores trend alignment (0-10).

    Awards points for incorporating current fashion trends.
    """
    txt = json_text(outfit)
    s = 6.0  # baseline

    # Accumulate trend matches with weights
    trend_bonus = sum(
        t["w"] for t in trend_tags
        if t["tag"].lower() in txt
    )

    s += min(3.0, trend_bonus * 1.5)

    return clamp(s)


def final_score(outfit: dict, items: List[dict], ctx: dict) -> float:
    """
    Computes the final weighted score for an outfit.

    Args:
        outfit: The outfit dict from LLM output
        items: The enriched items list from agentic layer
        ctx: The context pack with all metadata

    Returns:
        Final score (0-10) rounded to 2 decimal places
    """
    scores = {
        "weather": score_weather(outfit, ctx["weather_compact"], ctx["derived"]),
        "occasion": score_occasion(outfit, ctx["session"]["occasion"], ctx["session"]["vibe"]),
        "color": score_color(outfit, ctx["user_profile"]),
        "fit_body": score_fit_body(outfit, ctx["user_profile"]),
        "brand_budget": score_brand_budget(items, ctx["user_profile"].get("brand_prefs", []), ctx["constraints"]["budget"]),
        "trend": score_trend(outfit, ctx["trend_tags"])
    }

    # Compute weighted sum
    weighted_sum = sum(WEIGHTS[k] * scores[k] for k in WEIGHTS.keys())

    # Optional: blend small % of model's suggestion to break ties
    s_model = outfit.get("score_suggestion")
    if s_model is not None:
        final = 0.95 * weighted_sum + 0.05 * s_model
    else:
        final = weighted_sum

    return round(final, 2)
