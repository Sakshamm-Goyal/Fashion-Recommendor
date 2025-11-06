# config.py
"""
Configuration for Elara AI Personal Stylist.
All sensitive values should be set via environment variables.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# OpenAI Configuration
# ============================================================================
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_REASONING_MODEL = os.environ.get("OPENAI_REASONING_MODEL", "gpt-4o")  # Main stylist reasoning
OPENAI_MINI_MODEL = os.environ.get("OPENAI_MINI_MODEL", "gpt-4o-mini")       # Product reranking
OPENAI_EMBED_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-large")  # Vector embeddings

# ============================================================================
# Weather API Configuration
# ============================================================================
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")
WEATHER_UNITS = os.environ.get("WEATHER_UNITS", "metric")  # metric/imperial
DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "USD")

# ============================================================================
# Infrastructure Configuration
# ============================================================================
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6380/0")
PG_DSN = os.environ.get("PG_DSN", "postgresql://elara:elara@localhost:5435/elara")

# ============================================================================
# Product Search API Configuration
# ============================================================================

def is_valid_api_key(key: str, min_length: int = 20) -> bool:
    """
    Check if API key looks valid (not a placeholder).

    Args:
        key: The API key to validate
        min_length: Minimum length for a valid key

    Returns:
        True if key appears valid, False if it's a placeholder or invalid
    """
    if not key or len(key) < min_length:
        return False
    # Check for common placeholder patterns
    invalid_patterns = ['your_', 'example', 'placeholder', 'xxx', 'fake', 'test_key']
    return not any(pattern in key.lower() for pattern in invalid_patterns)

# Google Shopping API (via Custom Search)
GOOGLE_SHOPPING_API_KEY = os.environ.get("GOOGLE_SHOPPING_API_KEY", "")
GOOGLE_SHOPPING_CX = os.environ.get("GOOGLE_SHOPPING_CX", "")  # Custom Search Engine ID

# Validate Google Shopping credentials
HAS_VALID_GOOGLE_SHOPPING = (
    is_valid_api_key(GOOGLE_SHOPPING_API_KEY) and
    is_valid_api_key(GOOGLE_SHOPPING_CX, min_length=10)
)

# Affiliate Network APIs
RAKUTEN_API_KEY = os.environ.get("RAKUTEN_API_KEY", "")
RAKUTEN_ACCOUNT_ID = os.environ.get("RAKUTEN_ACCOUNT_ID", "")

IMPACT_API_KEY = os.environ.get("IMPACT_API_KEY", "")
IMPACT_ACCOUNT_ID = os.environ.get("IMPACT_ACCOUNT_ID", "")

SHARESALE_AFFILIATE_ID = os.environ.get("SHARESALE_AFFILIATE_ID", "")

# ============================================================================
# Rate Limiting & Performance
# ============================================================================
MAX_REQUESTS_PER_MINUTE = int(os.environ.get("MAX_REQUESTS_PER_MINUTE", "30"))

# Product Search Configuration
ENABLE_ASOS_SEARCH = os.environ.get("ENABLE_ASOS_SEARCH", "true").lower() == "true"  # Can disable if problematic

# ============================================================================
# Business Logic Configuration
# ============================================================================
RETAILER_ALLOWLIST = [
    "ASOS",
    "Nordstrom",
    "Macy's",
    "Amazon Fashion",
    "Urban Outfitters",
    "Revolve"
]

MAX_ONLINE_ITEMS_PER_LOOK = 3

# Default budget caps (if not specified by user)
DEFAULT_SOFT_CAP = 150  # USD
DEFAULT_HARD_CAP = 300  # USD
