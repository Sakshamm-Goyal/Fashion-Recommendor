# services/outfit_composer.py
"""
Outfit Composition Logic for Elara AI Personal Stylist.

Implements gender-specific outfit composition rules:
- Men: 5 parts (top, bottom, footwear + optional outerwear + 2-3 accessories)
- Women: 7-8 parts (footwear + either top/bottom OR one-piece + optional outerwear + 4-5 accessories + makeup)

Provides validation and missing item suggestions for complete outfit compositions.
"""
from typing import List, Dict, Literal, Optional
from contracts.models import CompositionItem, MakeupSuggestion

# ============================================================================
# Gender-Specific Composition Rules
# ============================================================================

MEN_COMPOSITION = {
    "required_slots": ["top", "bottom", "footwear"],
    "optional_slots": ["outerwear"],
    "accessory_range": (2, 3),  # Min 2, Max 3 accessories
    "total_parts": 5,
    "has_makeup": False,
}

WOMEN_COMPOSITION = {
    "required_slots": ["footwear"],
    "outfit_choice": ["top_bottom", "one_piece"],  # Either (top + bottom) OR one_piece
    "optional_slots": ["outerwear"],
    "accessory_range": (4, 5),  # Min 4, Max 5 accessories
    "total_parts_range": (7, 8),
    "has_makeup": True,
}

# ============================================================================
# Slot Definitions
# ============================================================================

MEN_SLOTS = {
    "top": ["shirt", "t-shirt", "polo", "sweater", "hoodie", "tank top", "henley"],
    "bottom": ["jeans", "chinos", "trousers", "shorts", "joggers", "dress pants"],
    "outerwear": ["jacket", "blazer", "coat", "bomber", "cardigan", "vest"],
    "footwear": ["sneakers", "boots", "loafers", "dress shoes", "sandals", "oxfords"],
    "accessory": ["watch", "belt", "sunglasses", "hat", "scarf", "bag", "bracelet", "necklace"],
}

WOMEN_SLOTS = {
    "top": ["blouse", "shirt", "t-shirt", "sweater", "crop top", "tank top", "cami", "turtleneck"],
    "bottom": ["jeans", "trousers", "skirt", "shorts", "leggings", "culottes", "palazzo pants"],
    "one_piece": ["dress", "jumpsuit", "romper", "maxi dress", "midi dress", "mini dress"],
    "outerwear": ["jacket", "blazer", "coat", "cardigan", "kimono", "duster", "trench coat"],
    "footwear": ["heels", "flats", "sandals", "boots", "sneakers", "mules", "wedges", "loafers"],
    "accessory": ["handbag", "clutch", "sunglasses", "jewelry", "scarf", "hat", "belt", "watch", "earrings", "necklace", "bracelet", "ring"],
}

# ============================================================================
# Makeup Suggestions by Occasion
# ============================================================================

MAKEUP_BY_OCCASION = {
    "formal": {
        "style": "glamorous",
        "focus": "overall",
        "color_palette": ["neutral", "classic", "smokey"],
        "description": "Polished and sophisticated with classic tones. Defined eyes and lips for an elegant finish.",
    },
    "business": {
        "style": "natural",
        "focus": "overall",
        "color_palette": ["neutral", "warm", "soft"],
        "description": "Professional and understated. Natural tones with subtle definition for a polished look.",
    },
    "casual": {
        "style": "minimal",
        "focus": "none",
        "color_palette": ["natural", "fresh"],
        "description": "Fresh-faced and effortless. Light coverage with a hint of color for everyday wear.",
    },
    "date_night": {
        "style": "glamorous",
        "focus": "lips",
        "color_palette": ["rose", "berry", "warm"],
        "description": "Romantic and alluring with emphasis on lips. Soft, glowing skin with a pop of color.",
    },
    "party": {
        "style": "dramatic",
        "focus": "eyes",
        "color_palette": ["smokey", "metallic", "bold"],
        "description": "Bold and eye-catching with dramatic eyes. Statement makeup for a memorable look.",
    },
    "outdoor": {
        "style": "light",
        "focus": "overall",
        "color_palette": ["natural", "sun-kissed", "fresh"],
        "description": "Light and breathable for outdoor activities. Natural finish with sun protection.",
    },
    "default": {
        "style": "natural",
        "focus": "overall",
        "color_palette": ["neutral", "natural"],
        "description": "Balanced and versatile. Natural beauty enhanced with subtle definition.",
    },
}

# ============================================================================
# Validation Functions
# ============================================================================

def validate_composition(
    composition: List[CompositionItem],
    gender: Literal["male", "female"],
    occasion: Optional[str] = None
) -> Dict[str, any]:
    """
    Validate outfit composition against gender-specific rules.

    Args:
        composition: List of CompositionItem objects
        gender: User's gender ("male" or "female")
        occasion: Optional occasion for makeup suggestion (women only)

    Returns:
        Dictionary with validation results:
        {
            "is_valid": bool,
            "missing_slots": List[str],
            "errors": List[str],
            "warnings": List[str],
            "makeup_suggestion": Optional[MakeupSuggestion]
        }
    """
    errors = []
    warnings = []
    missing_slots = []

    # Extract slot counts
    slot_counts = {}
    for item in composition:
        slot_counts[item.slot] = slot_counts.get(item.slot, 0) + 1

    # Gender-specific validation
    if gender == "male":
        result = _validate_men_composition(composition, slot_counts)
        makeup_suggestion = None
    else:  # female
        result = _validate_women_composition(composition, slot_counts, occasion)
        makeup_suggestion = result.get("makeup_suggestion")

    return {
        "is_valid": result["is_valid"],
        "missing_slots": result.get("missing_slots", []),
        "errors": result.get("errors", []),
        "warnings": result.get("warnings", []),
        "makeup_suggestion": makeup_suggestion,
    }


def _validate_men_composition(
    composition: List[CompositionItem],
    slot_counts: Dict[str, int]
) -> Dict[str, any]:
    """Validate men's outfit composition (5 parts)."""
    errors = []
    warnings = []
    missing_slots = []

    # Check required slots
    for slot in MEN_COMPOSITION["required_slots"]:
        if slot not in slot_counts:
            missing_slots.append(slot)
            errors.append(f"Missing required slot: {slot}")

    # Check accessory count
    accessory_count = slot_counts.get("accessory", 0)
    min_acc, max_acc = MEN_COMPOSITION["accessory_range"]

    if accessory_count < min_acc:
        warnings.append(f"Only {accessory_count} accessories (recommended: {min_acc}-{max_acc})")
    elif accessory_count > max_acc:
        warnings.append(f"Too many accessories: {accessory_count} (recommended: {min_acc}-{max_acc})")

    # Check total parts
    total_parts = len(composition)
    if total_parts != MEN_COMPOSITION["total_parts"]:
        warnings.append(f"Total parts: {total_parts} (recommended: {MEN_COMPOSITION['total_parts']})")

    # Check for invalid slots
    for slot in slot_counts.keys():
        if slot not in MEN_SLOTS and slot != "accessory":
            errors.append(f"Invalid slot for men's outfit: {slot}")

    is_valid = len(errors) == 0

    return {
        "is_valid": is_valid,
        "missing_slots": missing_slots,
        "errors": errors,
        "warnings": warnings,
    }


def _validate_women_composition(
    composition: List[CompositionItem],
    slot_counts: Dict[str, int],
    occasion: Optional[str] = None
) -> Dict[str, any]:
    """Validate women's outfit composition (7-8 parts + makeup)."""
    errors = []
    warnings = []
    missing_slots = []

    # Check required slots
    for slot in WOMEN_COMPOSITION["required_slots"]:
        if slot not in slot_counts:
            missing_slots.append(slot)
            errors.append(f"Missing required slot: {slot}")

    # Check outfit choice: (top + bottom) OR one_piece
    has_top = "top" in slot_counts
    has_bottom = "bottom" in slot_counts
    has_one_piece = "one_piece" in slot_counts

    if has_one_piece:
        if has_top or has_bottom:
            warnings.append("Outfit has one-piece AND top/bottom (unusual combination)")
    else:
        if not has_top:
            missing_slots.append("top")
            errors.append("Missing top (required when not wearing one-piece)")
        if not has_bottom:
            missing_slots.append("bottom")
            errors.append("Missing bottom (required when not wearing one-piece)")

    # Check accessory count
    accessory_count = slot_counts.get("accessory", 0)
    min_acc, max_acc = WOMEN_COMPOSITION["accessory_range"]

    if accessory_count < min_acc:
        warnings.append(f"Only {accessory_count} accessories (recommended: {min_acc}-{max_acc})")
    elif accessory_count > max_acc:
        warnings.append(f"Too many accessories: {accessory_count} (recommended: {min_acc}-{max_acc})")

    # Check total parts
    total_parts = len(composition)
    min_parts, max_parts = WOMEN_COMPOSITION["total_parts_range"]
    if total_parts < min_parts:
        warnings.append(f"Only {total_parts} parts (recommended: {min_parts}-{max_parts})")
    elif total_parts > max_parts:
        warnings.append(f"Too many parts: {total_parts} (recommended: {min_parts}-{max_parts})")

    # Check for invalid slots
    for slot in slot_counts.keys():
        if slot not in WOMEN_SLOTS and slot != "accessory":
            errors.append(f"Invalid slot for women's outfit: {slot}")

    # Generate makeup suggestion
    makeup_suggestion = _generate_makeup_suggestion(occasion)

    is_valid = len(errors) == 0

    return {
        "is_valid": is_valid,
        "missing_slots": missing_slots,
        "errors": errors,
        "warnings": warnings,
        "makeup_suggestion": makeup_suggestion,
    }


def _generate_makeup_suggestion(occasion: Optional[str] = None) -> MakeupSuggestion:
    """Generate makeup suggestion based on occasion."""
    # Normalize occasion
    occasion_key = "default"
    if occasion:
        occasion_lower = occasion.lower()
        if any(kw in occasion_lower for kw in ["formal", "gala", "wedding", "black tie"]):
            occasion_key = "formal"
        elif any(kw in occasion_lower for kw in ["business", "work", "office", "professional"]):
            occasion_key = "business"
        elif any(kw in occasion_lower for kw in ["date", "dinner", "romantic"]):
            occasion_key = "date_night"
        elif any(kw in occasion_lower for kw in ["party", "club", "night out", "celebration"]):
            occasion_key = "party"
        elif any(kw in occasion_lower for kw in ["outdoor", "picnic", "beach", "hiking"]):
            occasion_key = "outdoor"
        elif any(kw in occasion_lower for kw in ["casual", "everyday", "relaxed"]):
            occasion_key = "casual"

    makeup_data = MAKEUP_BY_OCCASION[occasion_key]

    return MakeupSuggestion(
        style=makeup_data["style"],
        focus=makeup_data["focus"],
        color_palette=makeup_data["color_palette"],
        description=makeup_data["description"]
    )


def suggest_missing_items(
    composition: List[CompositionItem],
    gender: Literal["male", "female"]
) -> List[str]:
    """
    Suggest missing items to complete an outfit.

    Args:
        composition: Current outfit composition
        gender: User's gender

    Returns:
        List of item suggestions (e.g., ["Add a belt", "Consider a watch"])
    """
    suggestions = []

    slot_counts = {}
    for item in composition:
        slot_counts[item.slot] = slot_counts.get(item.slot, 0) + 1

    if gender == "male":
        # Check required slots
        if "top" not in slot_counts:
            suggestions.append("Add a top (shirt, t-shirt, or sweater)")
        if "bottom" not in slot_counts:
            suggestions.append("Add bottoms (jeans, chinos, or trousers)")
        if "footwear" not in slot_counts:
            suggestions.append("Add footwear (sneakers, boots, or dress shoes)")

        # Check accessories
        accessory_count = slot_counts.get("accessory", 0)
        if accessory_count < MEN_COMPOSITION["accessory_range"][0]:
            needed = MEN_COMPOSITION["accessory_range"][0] - accessory_count
            suggestions.append(f"Add {needed} accessory/accessories (watch, belt, sunglasses, etc.)")

        # Suggest outerwear for layering
        if "outerwear" not in slot_counts:
            suggestions.append("Consider adding outerwear for layering (jacket, blazer, or coat)")

    else:  # female
        # Check footwear
        if "footwear" not in slot_counts:
            suggestions.append("Add footwear (heels, flats, boots, or sandals)")

        # Check outfit choice
        has_one_piece = "one_piece" in slot_counts
        has_top = "top" in slot_counts
        has_bottom = "bottom" in slot_counts

        if not has_one_piece:
            if not has_top:
                suggestions.append("Add a top (blouse, shirt, or sweater)")
            if not has_bottom:
                suggestions.append("Add bottoms (jeans, skirt, or trousers)")

        # Check accessories
        accessory_count = slot_counts.get("accessory", 0)
        if accessory_count < WOMEN_COMPOSITION["accessory_range"][0]:
            needed = WOMEN_COMPOSITION["accessory_range"][0] - accessory_count
            suggestions.append(f"Add {needed} accessory/accessories (handbag, jewelry, sunglasses, etc.)")

        # Suggest outerwear for layering
        if "outerwear" not in slot_counts:
            suggestions.append("Consider adding outerwear for layering (jacket, blazer, or cardigan)")

    return suggestions


def get_slot_examples(gender: Literal["male", "female"], slot: str) -> List[str]:
    """
    Get example items for a specific slot based on gender.

    Args:
        gender: User's gender
        slot: Slot name (e.g., "top", "bottom", "footwear")

    Returns:
        List of example items for the slot
    """
    slots_dict = MEN_SLOTS if gender == "male" else WOMEN_SLOTS
    return slots_dict.get(slot, [])


def format_composition_summary(composition: List[CompositionItem]) -> str:
    """
    Format composition as a readable summary.

    Args:
        composition: List of CompositionItem objects

    Returns:
        Formatted string summary
    """
    lines = []

    # Group by slot
    by_slot = {}
    for item in composition:
        if item.slot not in by_slot:
            by_slot[item.slot] = []
        by_slot[item.slot].append(item)

    # Format each slot
    slot_order = ["top", "bottom", "one_piece", "outerwear", "footwear", "accessory"]

    for slot in slot_order:
        if slot in by_slot:
            items = by_slot[slot]
            for i, item in enumerate(items, 1):
                if item.source == "wardrobe":
                    source_label = f"[Wardrobe: {item.wardrobe_item_id}]"
                else:
                    source_label = f"[Online: {item.descriptor}]"

                if len(items) > 1:
                    lines.append(f"  {slot.capitalize()} {i}: {source_label}")
                else:
                    lines.append(f"  {slot.capitalize()}: {source_label}")

    return "\n".join(lines)
