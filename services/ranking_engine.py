# services/ranking_engine.py
"""
Advanced Product Ranking Engine.

Uses multi-signal scoring to rank products for relevance, quality, and user fit.
Can be extended with ML models (XGBoost/LightGBM) in future.
"""
from typing import List, Dict, Optional
from contracts.models import Product


class RankingEngine:
    """
    Multi-signal product ranking engine.
    """

    def __init__(self):
        """Initialize ranking engine with configurable weights."""
        self.weights = {
            "semantic_relevance": 0.30,  # Vector similarity
            "price_fit": 0.20,            # Budget alignment
            "availability": 0.15,          # In-stock, fast shipping
            "brand_match": 0.10,           # User brand preferences
            "quality_signals": 0.10,       # Reviews/ratings
            "trend_alignment": 0.05,       # Fashion trends
            "sustainability": 0.05,        # Eco-friendly
            "return_policy": 0.05,         # Easy returns
        }

    def rank_products(
        self,
        products: List[Product],
        context: Dict
    ) -> List[Product]:
        """
        Rank products using multi-signal scoring.

        Args:
            products: List of Product objects to rank
            context: User context with budget, preferences, occasion, etc.

        Returns:
            List of products sorted by relevance score (descending)
        """
        scored_products = []

        for product in products:
            score = self._compute_rank_score(product, context)
            product.relevance_score = score  # Update product's relevance score
            scored_products.append((score, product))

        # Sort by score (descending)
        scored_products.sort(key=lambda x: x[0], reverse=True)

        return [product for score, product in scored_products]

    def _compute_rank_score(self, product: Product, context: Dict) -> float:
        """
        Compute overall rank score for a product.

        Returns:
            Score between 0-1 (higher is better)
        """
        scores = {}

        # 1. Semantic Relevance
        scores["semantic_relevance"] = product.relevance_score or 0.5

        # 2. Price Fit
        budget = context.get("budget", {})
        scores["price_fit"] = self._score_price_fit(
            product.price,
            budget.get("soft_cap", 150),
            budget.get("hard_cap", 300)
        )

        # 3. Availability
        scores["availability"] = self._score_availability(product)

        # 4. Brand Match
        brand_prefs = context.get("brand_prefs", [])
        scores["brand_match"] = self._score_brand_match(product.brand, brand_prefs)

        # 5. Quality Signals (reviews/ratings)
        scores["quality_signals"] = self._score_quality(product)

        # 6. Trend Alignment
        trend_tags = context.get("trend_tags", [])
        scores["trend_alignment"] = self._score_trend_alignment(product, trend_tags)

        # 7. Sustainability
        scores["sustainability"] = self._score_sustainability(product)

        # 8. Return Policy
        scores["return_policy"] = self._score_return_policy(product.retailer)

        # Weighted sum
        total_score = sum(
            self.weights[key] * scores[key]
            for key in self.weights
        )

        return round(total_score, 3)

    def _score_price_fit(self, price: float, soft_cap: float, hard_cap: float) -> float:
        """Score how well price fits budget (0-1)."""
        if price > hard_cap:
            return 0.0

        if price <= soft_cap:
            # Sweet spot: at or under soft cap
            # Score: 0.8 to 1.0 (closer to soft cap = better value)
            return min(1.0, 0.8 + (price / soft_cap) * 0.2)

        # Between soft and hard cap: linearly decrease
        excess = price - soft_cap
        max_excess = hard_cap - soft_cap
        penalty = (excess / max_excess) * 0.6
        return max(0.2, 0.8 - penalty)

    def _score_availability(self, product: Product) -> float:
        """Score availability (in-stock, shipping speed)."""
        score = 0.0

        # In stock
        if product.in_stock:
            score += 0.7

        # Shipping speed
        if product.shipping_days:
            if product.shipping_days <= 2:
                score += 0.3  # Fast shipping
            elif product.shipping_days <= 5:
                score += 0.2  # Standard shipping
            else:
                score += 0.1  # Slow shipping
        else:
            score += 0.15  # Unknown, assume standard

        return min(1.0, score)

    def _score_brand_match(self, brand: Optional[str], preferred_brands: List[str]) -> float:
        """Score brand preference match."""
        if not preferred_brands or not brand:
            return 0.5  # Neutral

        # Exact match
        if brand in preferred_brands:
            return 1.0

        # Partial match (case-insensitive)
        brand_lower = brand.lower()
        for pref in preferred_brands:
            if pref.lower() in brand_lower or brand_lower in pref.lower():
                return 0.8

        return 0.3  # Non-preferred brand

    def _score_quality(self, product: Product) -> float:
        """Score product quality signals (reviews, ratings)."""
        score = 0.5  # Default neutral

        if product.rating:
            # Normalize rating (0-5 stars → 0-1 score)
            rating_score = product.rating / 5.0

            # Weight by number of reviews (more reviews = more trustworthy)
            if product.review_count:
                if product.review_count >= 100:
                    confidence = 1.0
                elif product.review_count >= 50:
                    confidence = 0.9
                elif product.review_count >= 10:
                    confidence = 0.7
                else:
                    confidence = 0.5

                score = rating_score * confidence + (1 - confidence) * 0.5
            else:
                score = rating_score * 0.7 + 0.3 * 0.5  # Some discount for unknown review count

        return score

    def _score_trend_alignment(self, product: Product, trend_tags: List[str]) -> float:
        """Score alignment with current fashion trends."""
        if not trend_tags:
            return 0.5

        # Check if product mentions trend keywords
        product_text = f"{product.title} {product.fabric or ''} {product.color or ''}".lower()

        matching_trends = 0
        for trend in trend_tags:
            if trend.lower() in product_text:
                matching_trends += 1

        if not matching_trends:
            return 0.3  # Not trendy

        # Normalize: more matching trends = higher score
        trend_score = min(1.0, 0.5 + (matching_trends / len(trend_tags)) * 0.5)
        return trend_score

    def _score_sustainability(self, product: Product) -> float:
        """Score sustainability (natural fabrics, ethical brands)."""
        score = 0.5  # Default neutral

        # Check for sustainable fabrics
        sustainable_fabrics = ["organic cotton", "linen", "hemp", "tencel", "recycled polyester"]
        if product.fabric:
            fabric_lower = product.fabric.lower()
            for sustainable in sustainable_fabrics:
                if sustainable in fabric_lower:
                    score = 0.9
                    break

        # Check for fast fashion brands (lower score)
        fast_fashion_brands = ["shein", "forever 21", "boohoo"]
        if product.brand:
            brand_lower = product.brand.lower()
            for fast in fast_fashion_brands:
                if fast in brand_lower:
                    score = 0.2
                    break

        return score

    def _score_return_policy(self, retailer: str) -> float:
        """Score return policy friendliness by retailer."""
        # Known good return policies
        good_returns = {
            "nordstrom": 1.0,  # Excellent, no questions asked
            "zappos": 1.0,
            "asos": 0.9,       # 28 days
            "amazon": 0.9,
            "macys": 0.8,
            "zara": 0.7,       # 30 days but can be strict
            "hm": 0.7,
        }

        retailer_lower = retailer.lower()
        for known, score in good_returns.items():
            if known in retailer_lower:
                return score

        return 0.5  # Unknown, assume average


# Global singleton
_ranking_engine = None


def get_ranking_engine() -> RankingEngine:
    """Get or create global ranking engine."""
    global _ranking_engine
    if _ranking_engine is None:
        _ranking_engine = RankingEngine()
    return _ranking_engine


# Convenience function
def rank_products(products: List[Product], context: Dict) -> List[Product]:
    """Quick function to rank products."""
    engine = get_ranking_engine()
    return engine.rank_products(products, context)
