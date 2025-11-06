# contracts/models.py
"""
Pydantic models for Elara AI Personal Stylist.
These models define the data contracts for wardrobe items, outfit compositions,
and LLM responses with strict validation for use with OpenAI Structured Outputs.
"""
from pydantic import BaseModel, Field, constr
from typing import List, Literal, Optional, Dict


class WardrobeItem(BaseModel):
    """
    Represents a single item in the user's wardrobe.
    Captures all metadata needed for outfit composition and personalization.
    """
    id: str
    brand: Optional[str] = None
    name: str
    category: str
    subcategory: Optional[str] = None
    dress_codes: List[str] = []
    seasons: List[str] = []
    colors: List[str] = []
    fit: Optional[str] = None
    length: Optional[str] = None
    sleeve_length: Optional[str] = None
    fabrics: List[str] = []
    tags: List[str] = []
    weather_suitability: Optional[str] = None
    score: Optional[int] = 1
    image: Optional[str] = None


class CompositionItem(BaseModel):
    """
    A single piece in an outfit composition.
    Can reference either a wardrobe item or describe an item to source online.

    Enhanced with gap reasoning and budget guidance for intelligent shopping.
    """
    slot: Literal["top", "bottom", "outerwear", "footwear", "accessory"]
    source: Literal["wardrobe", "online"]
    wardrobe_item_id: Optional[str] = None
    needs_online_alt: bool = False
    descriptor: Optional[constr(strip_whitespace=True, min_length=3)] = None

    # NEW: Enhanced fields for intelligent shopping
    gap_reason: Optional[str] = None  # Why this item needs to be purchased
    budget_tier: Optional[Literal["budget", "mid", "premium"]] = None  # Price guidance
    impact_score: Optional[int] = Field(default=None, ge=1, le=10)  # Versatility with wardrobe (1-10)


class Outfit(BaseModel):
    """
    A complete outfit recommendation with reasoning and metadata.
    """
    name: constr(strip_whitespace=True, min_length=3)
    summary: str
    composition: List[CompositionItem] = Field(min_length=2)
    reasoning: Dict[str, str]
    tags: List[str] = []
    score_suggestion: Optional[float] = Field(default=None, ge=0, le=10)


class WardrobeGapAnalysis(BaseModel):
    """
    Analysis of wardrobe completeness and missing items.
    Used to guide intelligent shopping recommendations.
    """
    has_sufficient_items: bool  # Can we create good outfits with existing wardrobe?
    missing_categories: List[str] = []  # e.g., ["formal shoes", "blazer", "dress shirt"]
    gap_reasoning: str  # Why user needs these items
    high_impact_purchases: List[str] = []  # Top 3 strategic purchases that unlock most outfits


class OutfitResponse(BaseModel):
    """
    The complete response from the LLM reasoning layer.
    Must contain exactly 3 outfit recommendations.

    Enhanced with wardrobe gap analysis for intelligent shopping guidance.
    """
    wardrobe_analysis: Optional[WardrobeGapAnalysis] = None  # NEW: Gap analysis
    outfits: List[Outfit] = Field(min_length=3, max_length=3)


class Product(BaseModel):
    """
    Represents a product from any source (vector DB, APIs, scrapers).
    Unified model for all product search results.
    """
    id: str
    title: str
    price: float
    currency: str = "USD"
    url: str
    image: Optional[str] = None
    retailer: str
    brand: Optional[str] = None

    # Metadata
    category: Optional[str] = None
    subcategory: Optional[str] = None
    color: Optional[str] = None
    fabric: Optional[str] = None
    sizes_available: List[str] = []

    # Availability & Shipping
    in_stock: bool = True
    shipping_days: Optional[int] = None

    # Quality Signals
    rating: Optional[float] = Field(default=None, ge=0, le=5)  # 0-5 stars
    review_count: Optional[int] = None

    # Search Metadata
    source: Literal["vector_db", "google_shopping", "asos", "affiliate", "scraper", "chatgpt", "web_search"] = "vector_db"
    relevance_score: Optional[float] = None  # Semantic similarity or rank score

    # Affiliate
    affiliate_link: Optional[str] = None
    commission_rate: Optional[float] = None


class ProductSearchResult(BaseModel):
    """
    Result from product search with ranking and reasoning.
    """
    product: Product
    rank: int
    reasoning: Optional[str] = None  # Why LLM chose this product
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


def json_schema():
    """
    Returns the JSON schema for OutfitResponse for use with OpenAI Structured Outputs API.
    """
    return OutfitResponse.model_json_schema()
