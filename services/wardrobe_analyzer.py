# services/wardrobe_analyzer.py
"""
Wardrobe Gap Analysis Service.

Analyzes user's wardrobe to identify missing items for specific occasions,
provides high-impact purchase recommendations, and helps build a versatile wardrobe.

This service uses rule-based logic + optional LLM analysis for intelligent gap detection.
"""
from typing import List, Dict, Optional
from collections import defaultdict
from openai import OpenAI
import json
import config

client = OpenAI(api_key=config.OPENAI_API_KEY)


class WardrobeAnalyzer:
    """
    Intelligent wardrobe analyzer for gap detection.

    Analyzes wardrobe items against occasion requirements and identifies
    missing pieces that would have the highest impact.
    """

    # Essential items by occasion type
    OCCASION_REQUIREMENTS = {
        "office_professional": {
            "essential": ["blazer", "dress_pants", "dress_shoes", "button_down_shirt"],
            "nice_to_have": ["tie", "dress_belt", "leather_bag"],
        },
        "business_casual": {
            "essential": ["chinos", "polo_shirt", "loafers", "casual_blazer"],
            "nice_to_have": ["sweater", "oxford_shirt"],
        },
        "casual_everyday": {
            "essential": ["jeans", "t_shirt", "sneakers"],
            "nice_to_have": ["hoodie", "jacket", "casual_shoes"],
        },
        "date_night": {
            "essential": ["nice_pants", "fitted_shirt", "dress_shoes"],
            "nice_to_have": ["blazer", "watch", "cologne"],
        },
        "wedding_formal": {
            "essential": ["suit", "dress_shirt", "tie", "dress_shoes", "dress_belt"],
            "nice_to_have": ["cufflinks", "pocket_square", "watch"],
        },
        "gym_workout": {
            "essential": ["athletic_shorts", "workout_shirt", "athletic_shoes"],
            "nice_to_have": ["gym_bag", "water_bottle"],
        },
        "beach_vacation": {
            "essential": ["shorts", "t_shirt", "sandals", "swimsuit"],
            "nice_to_have": ["sunglasses", "hat", "beach_bag"],
        },
    }

    # Versatile items that work across multiple occasions
    VERSATILE_ITEMS = {
        "white_button_down": ["office_professional", "business_casual", "date_night"],
        "dark_jeans": ["business_casual", "casual_everyday", "date_night"],
        "navy_blazer": ["office_professional", "business_casual", "date_night"],
        "white_sneakers": ["casual_everyday", "date_night"],
        "chinos": ["office_professional", "business_casual", "date_night"],
    }

    def __init__(self):
        """Initialize wardrobe analyzer."""
        self.category_keywords = {
            "blazer": ["blazer", "sport coat", "jacket"],
            "dress_pants": ["dress pants", "trousers", "slacks"],
            "dress_shoes": ["oxford", "derby", "dress shoe", "loafer"],
            "button_down_shirt": ["button down", "dress shirt", "oxford shirt"],
            "chinos": ["chinos", "khakis"],
            "jeans": ["jeans", "denim"],
            "t_shirt": ["t-shirt", "tee", "crew neck"],
            "sneakers": ["sneakers", "trainers", "athletic shoes"],
            "suit": ["suit", "two-piece"],
        }

    def analyze_wardrobe_for_occasion(
        self,
        wardrobe_items: List[Dict],
        occasion: str,
        user_context: Optional[Dict] = None
    ) -> Dict:
        """
        Analyze wardrobe for a specific occasion.

        Args:
            wardrobe_items: List of user's wardrobe items
            occasion: Occasion type (e.g., "office_professional", "date_night")
            user_context: Optional user preferences, body type, etc.

        Returns:
            Analysis dict with gaps, recommendations, and strategy
        """
        # Normalize occasion to known types
        occasion_key = self._normalize_occasion(occasion)

        # Get requirements for this occasion
        requirements = self.OCCASION_REQUIREMENTS.get(
            occasion_key,
            {"essential": [], "nice_to_have": []}
        )

        # Categorize wardrobe items
        categorized_items = self._categorize_wardrobe(wardrobe_items)

        # Identify missing essentials
        missing_essentials = []
        for essential in requirements["essential"]:
            if essential not in categorized_items or len(categorized_items[essential]) == 0:
                missing_essentials.append(essential)

        # Identify missing nice-to-have
        missing_nice_to_have = []
        for nice in requirements["nice_to_have"]:
            if nice not in categorized_items or len(categorized_items[nice]) == 0:
                missing_nice_to_have.append(nice)

        # Determine if wardrobe is sufficient
        has_sufficient = len(missing_essentials) == 0

        # Identify high-impact purchases
        high_impact = self._identify_high_impact_purchases(
            missing_essentials,
            missing_nice_to_have,
            occasion_key
        )

        # Generate gap reasoning
        gap_reasoning = self._generate_gap_reasoning(
            occasion,
            missing_essentials,
            missing_nice_to_have,
            has_sufficient
        )

        return {
            "has_sufficient_items": has_sufficient,
            "missing_categories": missing_essentials + missing_nice_to_have,
            "missing_essentials": missing_essentials,
            "missing_nice_to_have": missing_nice_to_have,
            "gap_reasoning": gap_reasoning,
            "high_impact_purchases": high_impact,
            "existing_items": categorized_items,
        }

    def analyze_wardrobe_versatility(
        self,
        wardrobe_items: List[Dict]
    ) -> Dict:
        """
        Analyze overall wardrobe versatility.

        Identifies gaps in building a versatile wardrobe that works
        across multiple occasions.

        Args:
            wardrobe_items: List of user's wardrobe items

        Returns:
            Versatility analysis with recommendations
        """
        categorized_items = self._categorize_wardrobe(wardrobe_items)

        # Check for versatile items
        missing_versatile = []
        for item, occasions in self.VERSATILE_ITEMS.items():
            category = item.replace("_", " ")
            # Check if user has this versatile item
            found = False
            for cat_key, items in categorized_items.items():
                if category.lower() in cat_key.lower() and len(items) > 0:
                    found = True
                    break

            if not found:
                missing_versatile.append({
                    "item": item,
                    "occasions": occasions,
                    "impact": len(occasions)  # Impact = number of occasions it unlocks
                })

        # Sort by impact (descending)
        missing_versatile.sort(key=lambda x: x["impact"], reverse=True)

        return {
            "missing_versatile_items": missing_versatile,
            "versatility_score": self._calculate_versatility_score(
                categorized_items,
                missing_versatile
            ),
            "top_recommendations": missing_versatile[:3],  # Top 3 high-impact items
        }

    def _normalize_occasion(self, occasion: str) -> str:
        """
        Normalize occasion string to known occasion type.

        Args:
            occasion: Raw occasion string

        Returns:
            Normalized occasion key
        """
        occasion_lower = occasion.lower()

        # Mapping of keywords to occasion types
        mappings = {
            "office": "office_professional",
            "work": "office_professional",
            "professional": "office_professional",
            "business": "business_casual",
            "casual": "casual_everyday",
            "date": "date_night",
            "dinner": "date_night",
            "wedding": "wedding_formal",
            "formal": "wedding_formal",
            "gym": "gym_workout",
            "workout": "gym_workout",
            "beach": "beach_vacation",
            "vacation": "beach_vacation",
        }

        for keyword, occasion_type in mappings.items():
            if keyword in occasion_lower:
                return occasion_type

        # Default to business casual if unknown
        return "business_casual"

    def _categorize_wardrobe(self, wardrobe_items: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Categorize wardrobe items by type.

        Args:
            wardrobe_items: List of wardrobe items

        Returns:
            Dict mapping category to list of items
        """
        categorized = defaultdict(list)

        for item in wardrobe_items:
            item_text = f"{item.get('category', '')} {item.get('name', '')}".lower()

            # Try to match to known categories
            matched = False
            for category, keywords in self.category_keywords.items():
                for keyword in keywords:
                    if keyword.lower() in item_text:
                        categorized[category].append(item)
                        matched = True
                        break
                if matched:
                    break

            # If no match, use the item's own category
            if not matched and item.get('category'):
                categorized[item['category'].lower()].append(item)

        return dict(categorized)

    def _identify_high_impact_purchases(
        self,
        missing_essentials: List[str],
        missing_nice_to_have: List[str],
        occasion: str
    ) -> List[str]:
        """
        Identify high-impact purchases.

        Prioritize items that:
        1. Are essential for the occasion
        2. Are versatile across multiple occasions
        3. Fill critical gaps

        Args:
            missing_essentials: List of missing essential items
            missing_nice_to_have: List of missing nice-to-have items
            occasion: Occasion type

        Returns:
            Ordered list of high-impact purchases (top 3)
        """
        # Score each missing item
        scored_items = []

        for item in missing_essentials:
            score = 10  # Base score for essentials

            # Bonus if it's a versatile item
            if any(item in versatile_key for versatile_key in self.VERSATILE_ITEMS.keys()):
                score += 5

            scored_items.append((score, item, "essential"))

        for item in missing_nice_to_have:
            score = 5  # Base score for nice-to-have

            # Bonus if versatile
            if any(item in versatile_key for versatile_key in self.VERSATILE_ITEMS.keys()):
                score += 3

            scored_items.append((score, item, "nice_to_have"))

        # Sort by score
        scored_items.sort(key=lambda x: x[0], reverse=True)

        # Return top 3 item names
        return [item[1] for item in scored_items[:3]]

    def _generate_gap_reasoning(
        self,
        occasion: str,
        missing_essentials: List[str],
        missing_nice_to_have: List[str],
        has_sufficient: bool
    ) -> str:
        """
        Generate human-readable gap reasoning.

        Args:
            occasion: Occasion name
            missing_essentials: Missing essential items
            missing_nice_to_have: Missing nice-to-have items
            has_sufficient: Whether wardrobe is sufficient

        Returns:
            Gap reasoning string
        """
        if has_sufficient:
            if missing_nice_to_have:
                return (
                    f"Your wardrobe has the essentials for {occasion}, "
                    f"but could be elevated with: {', '.join(missing_nice_to_have[:2])}."
                )
            return f"Your wardrobe is well-equipped for {occasion}!"

        # Has gaps
        essential_str = ", ".join(missing_essentials[:2])
        return (
            f"For {occasion}, your wardrobe is missing some key pieces: {essential_str}. "
            f"Adding these would significantly improve your options for this occasion."
        )

    def _calculate_versatility_score(
        self,
        categorized_items: Dict[str, List[Dict]],
        missing_versatile: List[Dict]
    ) -> float:
        """
        Calculate overall wardrobe versatility score (0-100).

        Args:
            categorized_items: Categorized wardrobe items
            missing_versatile: Missing versatile items

        Returns:
            Versatility score (0-100)
        """
        total_versatile = len(self.VERSATILE_ITEMS)
        missing_count = len(missing_versatile)
        owned_versatile = total_versatile - missing_count

        # Base score from versatile items owned
        base_score = (owned_versatile / total_versatile) * 70

        # Bonus for wardrobe size (more items = more versatility)
        total_items = sum(len(items) for items in categorized_items.values())
        size_bonus = min(30, total_items * 2)  # Up to 30 points for size

        return min(100, base_score + size_bonus)


# Global singleton
_wardrobe_analyzer = None


def get_wardrobe_analyzer() -> WardrobeAnalyzer:
    """Get or create global wardrobe analyzer."""
    global _wardrobe_analyzer
    if _wardrobe_analyzer is None:
        _wardrobe_analyzer = WardrobeAnalyzer()
    return _wardrobe_analyzer


# Convenience functions
def analyze_for_occasion(
    wardrobe_items: List[Dict],
    occasion: str,
    user_context: Optional[Dict] = None
) -> Dict:
    """Quick function to analyze wardrobe for occasion."""
    analyzer = get_wardrobe_analyzer()
    return analyzer.analyze_wardrobe_for_occasion(wardrobe_items, occasion, user_context)


def analyze_versatility(wardrobe_items: List[Dict]) -> Dict:
    """Quick function to analyze wardrobe versatility."""
    analyzer = get_wardrobe_analyzer()
    return analyzer.analyze_wardrobe_versatility(wardrobe_items)
