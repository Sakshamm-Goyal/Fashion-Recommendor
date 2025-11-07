# services/product_enrichment.py
"""
Product Enrichment Module for Elara AI Personal Stylist.

Extracts and enriches product metadata from titles, descriptions, and other signals.
Uses keyword-based detection for:
- Category classification
- Fabric/material detection
- Fit type inference
- Brand extraction
- Quality signals
- Trend detection

No ML-based image analysis - accepts API limitations for now.
"""
from typing import Optional, List, Literal, Dict
from contracts.models import Product
import re


# ============================================================================
# Category Mapping
# ============================================================================

CATEGORY_KEYWORDS = {
    # Tops
    "shirt": ["shirt", "blouse", "button-up", "dress shirt", "button down"],
    "t-shirt": ["t-shirt", "tee", "tshirt", "tank top", "cami"],
    "sweater": ["sweater", "jumper", "pullover", "knit"],
    "hoodie": ["hoodie", "sweatshirt", "hoody"],
    "jacket": ["jacket", "blazer", "coat", "bomber", "windbreaker", "parka"],
    "cardigan": ["cardigan"],

    # Bottoms
    "jeans": ["jeans", "denim"],
    "pants": ["pants", "trousers", "chinos", "slacks"],
    "shorts": ["shorts"],
    "skirt": ["skirt"],
    "leggings": ["leggings", "tights"],

    # One-piece
    "dress": ["dress", "gown", "maxi", "midi"],
    "jumpsuit": ["jumpsuit", "romper", "playsuit"],

    # Footwear
    "sneakers": ["sneakers", "trainers", "athletic shoes", "running shoes"],
    "boots": ["boots", "booties", "ankle boots"],
    "heels": ["heels", "pumps", "stilettos"],
    "flats": ["flats", "ballet flats", "loafers"],
    "sandals": ["sandals", "slides", "flip flops"],

    # Accessories
    "bag": ["bag", "handbag", "purse", "clutch", "tote", "backpack"],
    "watch": ["watch", "timepiece"],
    "sunglasses": ["sunglasses", "shades"],
    "belt": ["belt"],
    "scarf": ["scarf", "shawl"],
    "hat": ["hat", "cap", "beanie"],
    "jewelry": ["jewelry", "necklace", "bracelet", "earrings", "ring"],
}

# ============================================================================
# Fabric/Material Detection
# ============================================================================

FABRIC_KEYWORDS = {
    # Natural fibers
    "cotton": ["cotton", "100% cotton", "organic cotton"],
    "wool": ["wool", "merino", "cashmere", "angora"],
    "silk": ["silk", "mulberry silk"],
    "linen": ["linen", "flax"],
    "leather": ["leather", "genuine leather", "suede"],

    # Synthetic fibers
    "polyester": ["polyester", "poly"],
    "nylon": ["nylon"],
    "spandex": ["spandex", "elastane", "lycra"],
    "acrylic": ["acrylic"],
    "rayon": ["rayon", "viscose"],

    # Blends
    "cotton_blend": ["cotton blend", "cotton poly", "cotton/polyester"],
    "wool_blend": ["wool blend", "wool/acrylic"],
}

# Premium fabrics for quality scoring
PREMIUM_FABRICS = ["silk", "cashmere", "merino", "leather", "linen", "wool"]

# ============================================================================
# Fit Type Detection
# ============================================================================

FIT_KEYWORDS = {
    "slim": ["slim", "slim fit", "fitted", "tailored", "skinny"],
    "regular": ["regular", "standard", "classic fit", "straight"],
    "relaxed": ["relaxed", "loose", "comfortable", "easy fit"],
    "oversized": ["oversized", "baggy", "boyfriend", "loose fit"],
}

# ============================================================================
# Quality Signals
# ============================================================================

QUALITY_SIGNALS = {
    "high": [
        "premium", "luxury", "designer", "high-quality", "handmade",
        "artisan", "bespoke", "couture", "italian made", "handcrafted"
    ],
    "medium": [
        "quality", "durable", "well-made", "crafted", "authentic"
    ],
    "budget": [
        "affordable", "budget", "value", "basic", "economy"
    ],
}

# ============================================================================
# Trend Keywords
# ============================================================================

TREND_KEYWORDS = [
    "trending", "viral", "popular", "bestseller", "best seller",
    "hot item", "must-have", "fashion-forward", "latest",
    "new arrival", "just in", "2024", "2025", "fw24", "ss25"
]

# ============================================================================
# Brand Detection
# ============================================================================

KNOWN_BRANDS = [
    # Luxury
    "Gucci", "Prada", "Louis Vuitton", "Chanel", "Dior", "Hermès",
    "Balenciaga", "Saint Laurent", "Givenchy", "Versace",

    # Designer
    "Ralph Lauren", "Calvin Klein", "Tommy Hilfiger", "Michael Kors",
    "Coach", "Kate Spade", "Marc Jacobs",

    # Contemporary
    "Zara", "H&M", "Uniqlo", "COS", "Mango", "Massimo Dutti",

    # Sportswear
    "Nike", "Adidas", "Puma", "Reebok", "Under Armour", "Lululemon",
    "Athleta", "Gymshark",

    # Fast Fashion
    "Forever 21", "Fashion Nova", "Shein", "Boohoo", "Missguided",

    # Premium Casual
    "Everlane", "Reformation", "Allbirds", "Patagonia", "Arc'teryx",
]


# ============================================================================
# Main Enrichment Function
# ============================================================================

def enrich_product(product: Product) -> Product:
    """
    Enrich product with extracted metadata.

    Args:
        product: Product object to enrich

    Returns:
        Enriched Product with filled metadata fields
    """
    text = f"{product.title} {product.brand or ''} {product.category or ''}".lower()

    # Extract category if missing
    if not product.category:
        product.category = _extract_category(text)

    # Extract subcategory
    if not product.subcategory:
        product.subcategory = _extract_subcategory(text, product.category)

    # Extract fabric/material
    if not product.fabric:
        product.fabric = _extract_fabric(text)

    # Extract fit type
    if not product.fit_type:
        product.fit_type = _extract_fit(text)

    # Extract/validate brand
    if not product.brand:
        product.brand = _extract_brand(product.title)

    # Calculate fabric quality score
    if not product.fabric_quality_score:
        product.fabric_quality_score = _calculate_fabric_quality(product.fabric, text)

    # Detect trend signals
    if not product.is_trending:
        product.is_trending = _detect_trending(text)

    # Extract color if missing
    if not product.color:
        product.color = _extract_color(text)

    return product


# ============================================================================
# Extraction Functions
# ============================================================================

def _extract_category(text: str) -> Optional[str]:
    """Extract category from product text."""
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return category
    return None


def _extract_subcategory(text: str, category: Optional[str]) -> Optional[str]:
    """Extract subcategory based on category and text."""
    if not category:
        return None

    subcategory_map = {
        "shirt": {
            "dress shirt": ["dress shirt", "button-up", "oxford"],
            "casual shirt": ["casual", "flannel", "chambray"],
        },
        "pants": {
            "chinos": ["chinos", "khakis"],
            "dress pants": ["dress pants", "slacks", "trousers"],
            "joggers": ["joggers", "sweatpants"],
        },
        "dress": {
            "maxi": ["maxi"],
            "midi": ["midi"],
            "mini": ["mini"],
        },
    }

    if category in subcategory_map:
        for subcat, keywords in subcategory_map[category].items():
            for keyword in keywords:
                if keyword in text:
                    return subcat

    return None


def _extract_fabric(text: str) -> Optional[str]:
    """Extract fabric/material from text."""
    for fabric, keywords in FABRIC_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return fabric.replace("_", " ").title()
    return None


def _extract_fit(text: str) -> Optional[Literal["slim", "regular", "relaxed", "oversized"]]:
    """Extract fit type from text."""
    for fit, keywords in FIT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return fit
    return None


def _extract_brand(title: str) -> Optional[str]:
    """Extract brand from title."""
    for brand in KNOWN_BRANDS:
        if brand.lower() in title.lower():
            return brand
    return None


def _extract_color(text: str) -> Optional[str]:
    """Extract color from text."""
    colors = [
        "black", "white", "gray", "grey", "navy", "blue", "red", "green",
        "yellow", "orange", "pink", "purple", "brown", "beige", "tan",
        "burgundy", "maroon", "olive", "khaki", "cream", "ivory"
    ]

    for color in colors:
        if color in text:
            return color.title()

    return None


def _calculate_fabric_quality(fabric: Optional[str], text: str) -> int:
    """
    Calculate fabric quality score (0-100).

    Args:
        fabric: Detected fabric type
        text: Full product text

    Returns:
        Quality score from 0-100
    """
    score = 50  # Base score

    # Premium fabric bonus
    if fabric and any(premium in fabric.lower() for premium in PREMIUM_FABRICS):
        score += 30

    # Quality signal bonus
    for quality_level, keywords in QUALITY_SIGNALS.items():
        for keyword in keywords:
            if keyword in text:
                if quality_level == "high":
                    score += 20
                elif quality_level == "medium":
                    score += 10
                elif quality_level == "budget":
                    score -= 10

    # Blend penalty (lower quality than pure)
    if fabric and "blend" in fabric.lower():
        score -= 10

    # Synthetic penalty
    if fabric and fabric.lower() in ["polyester", "nylon", "acrylic"]:
        score -= 15

    return max(0, min(100, score))  # Clamp to 0-100


def _detect_trending(text: str) -> bool:
    """Detect if product is trending."""
    return any(keyword in text for keyword in TREND_KEYWORDS)


# ============================================================================
# Batch Enrichment
# ============================================================================

def enrich_products(products: List[Product]) -> List[Product]:
    """
    Enrich multiple products.

    Args:
        products: List of Product objects

    Returns:
        List of enriched Products
    """
    return [enrich_product(product) for product in products]


# ============================================================================
# Quality Filtering
# ============================================================================

def filter_by_quality(products: List[Product], min_quality: int = 40) -> List[Product]:
    """
    Filter products by minimum fabric quality score.

    Args:
        products: List of products
        min_quality: Minimum quality score (0-100)

    Returns:
        Filtered list of products
    """
    return [
        p for p in products
        if p.fabric_quality_score and p.fabric_quality_score >= min_quality
    ]


def filter_by_availability(products: List[Product]) -> List[Product]:
    """
    Filter products to only in-stock items.

    Args:
        products: List of products

    Returns:
        Filtered list of in-stock products
    """
    return [
        p for p in products
        if p.availability_status == "in_stock"
    ]


# ============================================================================
# Utility Functions
# ============================================================================

def get_enrichment_summary(product: Product) -> Dict[str, any]:
    """
    Get summary of enrichment applied to a product.

    Args:
        product: Enriched product

    Returns:
        Dictionary with enrichment details
    """
    return {
        "category": product.category,
        "subcategory": product.subcategory,
        "fabric": product.fabric,
        "fit_type": product.fit_type,
        "fabric_quality_score": product.fabric_quality_score,
        "is_trending": product.is_trending,
        "color": product.color,
    }


def validate_enrichment(product: Product) -> Dict[str, bool]:
    """
    Validate enrichment completeness.

    Args:
        product: Product to validate

    Returns:
        Dictionary of validation checks
    """
    return {
        "has_category": product.category is not None,
        "has_fabric": product.fabric is not None,
        "has_fit_type": product.fit_type is not None,
        "has_quality_score": product.fabric_quality_score is not None,
        "has_color": product.color is not None,
    }
