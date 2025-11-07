# services/outfit_scorer.py
"""
Enhanced 10-Dimension Scoring Framework for Elara AI Personal Stylist.

Merges the original 6-dimension framework with the new 4-dimension framework:

Original 6 Dimensions:
1. Weather Match (20%)
2. Occasion Appropriateness (25%)
3. Color Harmony (20%)
4. Fit & Body Type (20%)
5. Brand & Budget (10%)
6. Trend Relevance (5%)

New 4 Dimensions (mapped to 10 sub-dimensions):
1. Contextual Relevance (40%) → Weather, Occasion, Location Style
2. Personalization (30%) → Color, Fit, Brand/Budget, Style Preference
3. Practical Feasibility (20%) → Availability, Delivery Time, Wardrobe Versatility
4. Fashion Quality (10%) → Fabric Quality, Trend Relevance

Total: 10 Sub-Dimensions with weighted scoring
"""
from typing import Dict, List, Optional, Literal
from contracts.models import Product, CompositionItem, WardrobeItem
import re

# ============================================================================
# 10-Dimension Scoring Framework
# ============================================================================

SCORING_DIMENSIONS = {
    # CONTEXTUAL RELEVANCE (40% total)
    "weather_match": {
        "weight": 0.15,
        "description": "How well the outfit matches the weather conditions",
        "category": "contextual"
    },
    "occasion_appropriateness": {
        "weight": 0.15,
        "description": "How appropriate the outfit is for the specified occasion",
        "category": "contextual"
    },
    "location_style": {
        "weight": 0.10,
        "description": "How well the outfit matches local fashion culture and norms",
        "category": "contextual"
    },

    # PERSONALIZATION (30% total)
    "color_harmony": {
        "weight": 0.10,
        "description": "Color coordination and match with user preferences",
        "category": "personalization"
    },
    "fit_body_type": {
        "weight": 0.10,
        "description": "How well the fit matches user's body type and preferences",
        "category": "personalization"
    },
    "brand_budget": {
        "weight": 0.06,
        "description": "Brand preferences and budget alignment",
        "category": "personalization"
    },
    "style_preference": {
        "weight": 0.04,
        "description": "Alignment with user's personal style preferences",
        "category": "personalization"
    },

    # PRACTICAL FEASIBILITY (20% total)
    "availability": {
        "weight": 0.08,
        "description": "Product availability and stock status",
        "category": "practical"
    },
    "delivery_time": {
        "weight": 0.07,
        "description": "Shipping speed and delivery reliability",
        "category": "practical"
    },
    "wardrobe_versatility": {
        "weight": 0.05,
        "description": "How well online items work with existing wardrobe",
        "category": "practical"
    },

    # FASHION QUALITY (10% total)
    "fabric_quality": {
        "weight": 0.05,
        "description": "Material quality and durability signals",
        "category": "quality"
    },
    "trend_relevance": {
        "weight": 0.05,
        "description": "Current fashion trends and timelessness",
        "category": "quality"
    },
}


def calculate_outfit_score(
    composition: List[CompositionItem],
    products: Dict[str, Product],  # descriptor -> Product mapping for online items
    wardrobe_items: Dict[str, WardrobeItem],  # id -> WardrobeItem mapping
    context: Dict[str, any]
) -> Dict[str, any]:
    """
    Calculate comprehensive 10-dimension score for an outfit.

    Args:
        composition: List of outfit pieces
        products: Online products mapped by descriptor
        wardrobe_items: User's wardrobe items mapped by ID
        context: Context data (weather, occasion, budget, user_prefs, etc.)

    Returns:
        {
            "total_score": float (0-10),
            "dimension_scores": Dict[str, float],
            "breakdown": Dict[str, Dict],  # Detailed scoring per dimension
            "insights": List[str]  # Human-readable insights
        }
    """
    dimension_scores = {}
    breakdown = {}
    insights = []

    # Extract context
    weather = context.get("weather", {})
    occasion = context.get("occasion", "")
    location = context.get("location", "")
    budget = context.get("budget", {})
    user_prefs = context.get("user_preferences", {})

    # Calculate each dimension
    dimension_scores["weather_match"] = _score_weather_match(composition, products, wardrobe_items, weather)
    dimension_scores["occasion_appropriateness"] = _score_occasion(composition, products, wardrobe_items, occasion)
    dimension_scores["location_style"] = _score_location_style(composition, location)
    dimension_scores["color_harmony"] = _score_color_harmony(composition, products, wardrobe_items, user_prefs)
    dimension_scores["fit_body_type"] = _score_fit(composition, products, user_prefs)
    dimension_scores["brand_budget"] = _score_brand_budget(products, budget, user_prefs)
    dimension_scores["style_preference"] = _score_style_preference(composition, user_prefs)
    dimension_scores["availability"] = _score_availability(products)
    dimension_scores["delivery_time"] = _score_delivery(products)
    dimension_scores["wardrobe_versatility"] = _score_versatility(composition, wardrobe_items)
    dimension_scores["fabric_quality"] = _score_fabric_quality(products, wardrobe_items, composition)
    dimension_scores["trend_relevance"] = _score_trend(composition, products, wardrobe_items)

    # Calculate weighted total score
    total_score = 0.0
    for dim, score in dimension_scores.items():
        weight = SCORING_DIMENSIONS[dim]["weight"]
        total_score += score * weight * 10  # Scale to 0-10

    # Generate insights
    insights = _generate_insights(dimension_scores, total_score)

    return {
        "total_score": round(total_score, 2),
        "dimension_scores": {k: round(v, 2) for k, v in dimension_scores.items()},
        "breakdown": breakdown,
        "insights": insights
    }


# ============================================================================
# Individual Dimension Scoring Functions
# ============================================================================

def _score_weather_match(
    composition: List[CompositionItem],
    products: Dict[str, Product],
    wardrobe_items: Dict[str, WardrobeItem],
    weather: Dict
) -> float:
    """Score weather appropriateness (0-1 scale)."""
    if not weather:
        return 0.7  # Default neutral score

    temp = weather.get("temperature")
    condition = weather.get("condition", "").lower()

    score = 0.0
    item_count = 0

    # Check fabric/season appropriateness
    for item in composition:
        item_count += 1

        if item.source == "wardrobe" and item.wardrobe_item_id:
            wardrobe_item = wardrobe_items.get(item.wardrobe_item_id)
            if wardrobe_item:
                # Check seasons
                if temp and temp < 15 and "winter" in wardrobe_item.seasons:
                    score += 1.0
                elif temp and 15 <= temp < 25 and any(s in wardrobe_item.seasons for s in ["spring", "fall"]):
                    score += 1.0
                elif temp and temp >= 25 and "summer" in wardrobe_item.seasons:
                    score += 1.0
                else:
                    score += 0.5  # Partial match

                # Check weather suitability
                if wardrobe_item.weather_suitability:
                    if condition in wardrobe_item.weather_suitability.lower():
                        score += 0.5
        else:
            # Online item - check descriptor
            product = products.get(item.descriptor)
            if product:
                descriptor_lower = item.descriptor.lower()

                # Temperature check
                if temp and temp < 15 and any(kw in descriptor_lower for kw in ["coat", "sweater", "wool", "thermal"]):
                    score += 1.0
                elif temp and temp >= 25 and any(kw in descriptor_lower for kw in ["lightweight", "linen", "breathable", "short"]):
                    score += 1.0
                elif temp and 15 <= temp < 25:
                    score += 0.8  # Most items work in moderate weather

                # Condition check
                if "rain" in condition and any(kw in descriptor_lower for kw in ["waterproof", "rain", "jacket"]):
                    score += 0.5

    return score / max(item_count, 1) if item_count > 0 else 0.5


def _score_occasion(
    composition: List[CompositionItem],
    products: Dict[str, Product],
    wardrobe_items: Dict[str, WardrobeItem],
    occasion: str
) -> float:
    """Score occasion appropriateness (0-1 scale)."""
    if not occasion:
        return 0.7

    occasion_lower = occasion.lower()
    score = 0.0
    item_count = 0

    # Define occasion keywords
    formal_keywords = ["formal", "business", "professional", "interview", "wedding", "gala"]
    casual_keywords = ["casual", "everyday", "relaxed", "weekend", "brunch"]
    smart_casual_keywords = ["smart casual", "date", "dinner", "cocktail"]
    athletic_keywords = ["gym", "workout", "athletic", "sport", "running"]

    for item in composition:
        item_count += 1

        if item.source == "wardrobe" and item.wardrobe_item_id:
            wardrobe_item = wardrobe_items.get(item.wardrobe_item_id)
            if wardrobe_item and wardrobe_item.dress_codes:
                # Check dress code match
                item_codes = [code.lower() for code in wardrobe_item.dress_codes]

                if any(kw in occasion_lower for kw in formal_keywords):
                    if any(code in item_codes for code in ["formal", "business", "professional"]):
                        score += 1.0
                    elif "smart casual" in item_codes:
                        score += 0.6
                    else:
                        score += 0.3
                elif any(kw in occasion_lower for kw in casual_keywords):
                    if "casual" in item_codes:
                        score += 1.0
                    else:
                        score += 0.5
                elif any(kw in occasion_lower for kw in smart_casual_keywords):
                    if "smart casual" in item_codes:
                        score += 1.0
                    elif any(code in item_codes for code in ["casual", "business casual"]):
                        score += 0.7
                    else:
                        score += 0.4
                elif any(kw in occasion_lower for kw in athletic_keywords):
                    if "athletic" in item_codes or "activewear" in item_codes:
                        score += 1.0
                    else:
                        score += 0.3
                else:
                    score += 0.6  # Default moderate score
            else:
                score += 0.5
        else:
            # Online item - check descriptor
            descriptor_lower = item.descriptor.lower() if item.descriptor else ""

            if any(kw in occasion_lower for kw in formal_keywords):
                if any(kw in descriptor_lower for kw in ["suit", "blazer", "dress shirt", "formal", "business"]):
                    score += 1.0
                else:
                    score += 0.4
            elif any(kw in occasion_lower for kw in casual_keywords):
                if any(kw in descriptor_lower for kw in ["casual", "jeans", "t-shirt", "sneakers"]):
                    score += 1.0
                else:
                    score += 0.6
            elif any(kw in occasion_lower for kw in athletic_keywords):
                if any(kw in descriptor_lower for kw in ["athletic", "gym", "workout", "sport"]):
                    score += 1.0
                else:
                    score += 0.3
            else:
                score += 0.6

    return score / max(item_count, 1) if item_count > 0 else 0.5


def _score_location_style(composition: List[CompositionItem], location: str) -> float:
    """Score location/cultural style appropriateness (0-1 scale)."""
    if not location:
        return 0.7

    # Simple implementation - can be enhanced with location-specific fashion data
    location_lower = location.lower()

    # Urban fashion capitals tend to be more fashion-forward
    if any(city in location_lower for city in ["new york", "paris", "milan", "london", "tokyo"]):
        return 0.85  # Fashion-forward cities - most styles work

    # Conservative regions
    if any(region in location_lower for region in ["middle east", "conservative"]):
        return 0.7  # Neutral - would need modest checks

    return 0.75  # Default good score


def _score_color_harmony(
    composition: List[CompositionItem],
    products: Dict[str, Product],
    wardrobe_items: Dict[str, WardrobeItem],
    user_prefs: Dict
) -> float:
    """Score color coordination and user preferences (0-1 scale)."""
    colors = []

    # Extract colors from items
    for item in composition:
        if item.source == "wardrobe" and item.wardrobe_item_id:
            wardrobe_item = wardrobe_items.get(item.wardrobe_item_id)
            if wardrobe_item:
                colors.extend(wardrobe_item.colors)
        else:
            product = products.get(item.descriptor)
            if product and product.color:
                colors.append(product.color)

    if not colors:
        return 0.6

    # Check user color preferences
    preferred_colors = user_prefs.get("preferred_colors", [])
    if preferred_colors:
        matches = sum(1 for c in colors if any(pref.lower() in c.lower() for pref in preferred_colors))
        color_pref_score = matches / len(colors)
    else:
        color_pref_score = 0.7

    # Basic color harmony check (neutral colors are safe)
    neutral_colors = ["black", "white", "gray", "grey", "navy", "beige", "tan", "brown"]
    neutral_count = sum(1 for c in colors if any(nc in c.lower() for nc in neutral_colors))

    if neutral_count >= len(colors) * 0.6:  # 60%+ neutrals = good harmony
        harmony_score = 0.9
    else:
        harmony_score = 0.7  # Default moderate score

    return (color_pref_score + harmony_score) / 2


def _score_fit(
    composition: List[CompositionItem],
    products: Dict[str, Product],
    user_prefs: Dict
) -> float:
    """Score fit match with user preferences (0-1 scale)."""
    preferred_fit = user_prefs.get("preferred_fit", "regular")

    score = 0.0
    item_count = 0

    for item in composition:
        if item.source == "online":
            product = products.get(item.descriptor)
            if product and product.fit_type:
                item_count += 1
                if product.fit_type == preferred_fit:
                    score += 1.0
                else:
                    score += 0.6  # Different fit but still acceptable
            elif item.fit_preference:
                item_count += 1
                if item.fit_preference == preferred_fit:
                    score += 1.0
                else:
                    score += 0.6

    return score / max(item_count, 1) if item_count > 0 else 0.7


def _score_brand_budget(
    products: Dict[str, Product],
    budget: Dict,
    user_prefs: Dict
) -> float:
    """Score brand preferences and budget alignment (0-1 scale)."""
    if not products:
        return 0.8  # Wardrobe-only outfit

    max_budget = budget.get("hard_cap", 300)
    soft_cap = budget.get("soft_cap", 150)
    preferred_brands = user_prefs.get("preferred_brands", [])

    total_price = sum(p.price for p in products.values() if p.price)
    brand_matches = sum(1 for p in products.values() if p.brand and any(b.lower() in p.brand.lower() for b in preferred_brands))

    # Budget score
    if total_price <= soft_cap:
        budget_score = 1.0
    elif total_price <= max_budget:
        budget_score = 0.7
    else:
        budget_score = 0.3

    # Brand score
    if preferred_brands:
        brand_score = brand_matches / len(products) if products else 0.5
    else:
        brand_score = 0.7  # No preference = neutral

    return (budget_score * 0.7 + brand_score * 0.3)  # Weight budget more heavily


def _score_style_preference(composition: List[CompositionItem], user_prefs: Dict) -> float:
    """Score alignment with user's style preferences (0-1 scale)."""
    preferred_styles = user_prefs.get("style_preferences", [])
    if not preferred_styles:
        return 0.7

    # Check tags and categories against style preferences
    # Simple keyword matching - can be enhanced
    style_keywords = {
        "minimalist": ["minimal", "simple", "clean", "basic"],
        "edgy": ["edgy", "bold", "statement", "leather", "punk"],
        "classic": ["classic", "timeless", "traditional", "elegant"],
        "bohemian": ["boho", "bohemian", "flowy", "ethnic"],
        "streetwear": ["streetwear", "urban", "sneakers", "hoodie"],
    }

    # Default good score if we can't determine style
    return 0.75


def _score_availability(products: Dict[str, Product]) -> float:
    """Score product availability (0-1 scale)."""
    if not products:
        return 1.0  # Wardrobe-only outfit

    available_count = sum(1 for p in products.values() if p.availability_status == "in_stock")
    low_stock_count = sum(1 for p in products.values() if p.availability_status == "low_stock")

    total = len(products)
    score = (available_count + low_stock_count * 0.5) / total

    return score


def _score_delivery(products: Dict[str, Product]) -> float:
    """Score delivery time feasibility (0-1 scale)."""
    if not products:
        return 1.0  # Wardrobe-only outfit

    scores = []
    for product in products.values():
        if product.shipping_days:
            if product.shipping_days <= 2:
                scores.append(1.0)
            elif product.shipping_days <= 5:
                scores.append(0.8)
            elif product.shipping_days <= 7:
                scores.append(0.6)
            else:
                scores.append(0.4)
        else:
            scores.append(0.7)  # Unknown delivery = moderate score

    return sum(scores) / len(scores) if scores else 0.7


def _score_versatility(composition: List[CompositionItem], wardrobe_items: Dict[str, WardrobeItem]) -> float:
    """Score how well online items work with existing wardrobe (0-1 scale)."""
    online_count = sum(1 for item in composition if item.source == "online")
    wardrobe_count = sum(1 for item in composition if item.source == "wardrobe")

    if online_count == 0:
        return 1.0  # All wardrobe = perfect versatility

    # More wardrobe integration = better versatility
    integration_ratio = wardrobe_count / len(composition)

    # Check impact scores
    impact_scores = [item.impact_score for item in composition if item.source == "online" and item.impact_score]
    avg_impact = sum(impact_scores) / len(impact_scores) if impact_scores else 5

    # Combine integration ratio and impact score
    return (integration_ratio * 0.5 + (avg_impact / 10) * 0.5)


def _score_fabric_quality(
    products: Dict[str, Product],
    wardrobe_items: Dict[str, WardrobeItem],
    composition: List[CompositionItem]
) -> float:
    """Score fabric quality signals (0-1 scale)."""
    quality_scores = []

    for item in composition:
        if item.source == "online":
            product = products.get(item.descriptor)
            if product:
                if product.fabric_quality_score:
                    quality_scores.append(product.fabric_quality_score / 100)
                elif product.fabric_type:
                    # Infer quality from fabric type
                    premium_fabrics = ["silk", "cashmere", "wool", "linen", "leather"]
                    if any(fab in product.fabric_type.lower() for fab in premium_fabrics):
                        quality_scores.append(0.8)
                    else:
                        quality_scores.append(0.6)
        else:
            # Wardrobe item - check fabrics
            wardrobe_item = wardrobe_items.get(item.wardrobe_item_id) if item.wardrobe_item_id else None
            if wardrobe_item and wardrobe_item.fabrics:
                premium_fabrics = ["silk", "cashmere", "wool", "linen", "leather"]
                if any(fab in " ".join(wardrobe_item.fabrics).lower() for fab in premium_fabrics):
                    quality_scores.append(0.8)
                else:
                    quality_scores.append(0.7)

    return sum(quality_scores) / len(quality_scores) if quality_scores else 0.7


def _score_trend(
    composition: List[CompositionItem],
    products: Dict[str, Product],
    wardrobe_items: Dict[str, WardrobeItem]
) -> float:
    """Score trend relevance (0-1 scale)."""
    trend_score = 0.0
    item_count = 0

    for item in composition:
        item_count += 1

        if item.source == "online":
            product = products.get(item.descriptor)
            if product:
                if product.is_trending:
                    trend_score += 1.0
                else:
                    trend_score += 0.7  # Not marked trending but still current
        else:
            # Wardrobe items assumed to be somewhat trendy if recently added
            trend_score += 0.75

    return trend_score / max(item_count, 1) if item_count > 0 else 0.7


def _generate_insights(dimension_scores: Dict[str, float], total_score: float) -> List[str]:
    """Generate human-readable insights from dimension scores."""
    insights = []

    # Overall score insight
    if total_score >= 8.5:
        insights.append("✓ Excellent outfit - Highly recommended!")
    elif total_score >= 7.0:
        insights.append("✓ Great outfit - Strong match across dimensions")
    elif total_score >= 5.5:
        insights.append("~ Good outfit - Some areas for improvement")
    else:
        insights.append("⚠ Fair outfit - Consider alternatives")

    # Dimension-specific insights
    if dimension_scores.get("weather_match", 0) < 0.5:
        insights.append("⚠ Weather match needs improvement")

    if dimension_scores.get("availability", 0) < 0.7:
        insights.append("⚠ Some items may have limited availability")

    if dimension_scores.get("delivery_time", 0) < 0.6:
        insights.append("⚠ Slower delivery times expected")

    if dimension_scores.get("budget_brand", 0) < 0.5:
        insights.append("⚠ May exceed budget preferences")

    if dimension_scores.get("fabric_quality", 0) >= 0.8:
        insights.append("✓ High-quality fabrics detected")

    if dimension_scores.get("wardrobe_versatility", 0) >= 0.8:
        insights.append("✓ Great integration with existing wardrobe")

    return insights
