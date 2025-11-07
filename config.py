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
# Helper Functions
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

# ============================================================================
# OpenAI Configuration
# ============================================================================
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_REASONING_MODEL = os.environ.get("OPENAI_REASONING_MODEL", "gpt-4o")  # Main stylist reasoning
OPENAI_MINI_MODEL = os.environ.get("OPENAI_MINI_MODEL", "gpt-4o-mini")       # Product reranking
OPENAI_EMBED_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-large")  # Vector embeddings

# ============================================================================
# Anthropic/Claude Configuration (for web search product enrichment)
# ============================================================================
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://ai.megallm.io")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4.5")
ANTHROPIC_SMALL_FAST_MODEL = os.environ.get("ANTHROPIC_SMALL_FAST_MODEL", "claude-3.7-sonnet")
MEGALLM_API_KEY = os.environ.get("MEGALLM_API_KEY", ANTHROPIC_API_KEY)  # Fallback to ANTHROPIC_API_KEY
ENABLE_CLAUDE_WEB_SEARCH = os.environ.get("ENABLE_CLAUDE_WEB_SEARCH", "true").lower() == "true" and is_valid_api_key(ANTHROPIC_API_KEY)

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

# Oxylabs Web Scraper API - PRIMARY SOURCE (Replaces SearchAPI)
# Uses Oxylabs to scrape Google Shopping and bypass anti-bot protection
OXYLABS_USERNAME = os.environ.get("OXYLABS_USERNAME", "elara_u1y0M")
OXYLABS_PASSWORD = os.environ.get("OXYLABS_PASSWORD", "AVFGxj4K3fx8n+i")
ENABLE_OXYLABS = os.environ.get("ENABLE_OXYLABS", "true").lower() == "true" and bool(OXYLABS_USERNAME and OXYLABS_PASSWORD)

# SearchAPI.io (Google Shopping API) - DEPRECATED (Rate limited, replaced by Oxylabs)
# Uses Google Shopping API to fetch products with real merchant links
SEARCHAPI_KEY = os.environ.get("SEARCHAPI_KEY", "XQjhjp62GegUDeZ6LZwwAGhB")  # Default key provided
SEARCHAPI_BASE_URL = os.environ.get("SEARCHAPI_BASE_URL", "https://www.searchapi.io/api/v1/search")
SEARCHAPI_DEFAULT_GL = os.environ.get("SEARCHAPI_DEFAULT_GL", "us")  # Country code
SEARCHAPI_DEFAULT_HL = os.environ.get("SEARCHAPI_DEFAULT_HL", "en")  # Language code
ENABLE_SEARCHAPI = os.environ.get("ENABLE_SEARCHAPI", "false").lower() == "true" and is_valid_api_key(SEARCHAPI_KEY)

# Retailed.io (DISABLED - API returning 500 errors)
RETAILED_API_KEY = os.environ.get("RETAILED_API_KEY", "")
RETAILED_BASE_URL = os.environ.get("RETAILED_BASE_URL", "https://app.retailed.io/api/v1/scraper")
ENABLE_RETAILED = os.environ.get("ENABLE_RETAILED", "false").lower() == "true" and is_valid_api_key(RETAILED_API_KEY)

# Retailed.io Supported Retailers
RETAILED_SUPPORTED_RETAILERS = [
    "nike", "zara", "forever21", "uniqlo", "dior", "farfetch",
    "macys", "zalando", "stockx", "goat", "stadium goods"
]

# Retailed.io Credit Budget
RETAILED_CREDIT_WARNING_THRESHOLD = int(os.environ.get("RETAILED_CREDIT_WARNING_THRESHOLD", "1000"))
RETAILED_MAX_REQUESTS_PER_SESSION = int(os.environ.get("RETAILED_MAX_REQUESTS_PER_SESSION", "20"))

# Google Shopping API (via Custom Search) - LEGACY
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
# Link Verification Agent Configuration (NEW)
# ============================================================================
# Enable real-time link verification using Playwright
ENABLE_LINK_VERIFICATION = os.environ.get("ENABLE_LINK_VERIFICATION", "true").lower() == "true"

# Verification performance settings
VERIFICATION_BATCH_SIZE = int(os.environ.get("VERIFICATION_BATCH_SIZE", "20"))  # Products to verify per batch
VERIFICATION_TIMEOUT = int(os.environ.get("VERIFICATION_TIMEOUT", "5000"))  # Milliseconds per product
VERIFICATION_CONCURRENCY = int(os.environ.get("VERIFICATION_CONCURRENCY", "5"))  # Parallel browser instances
VERIFICATION_CACHE_TTL = int(os.environ.get("VERIFICATION_CACHE_TTL", "3600"))  # Cache TTL in seconds (1 hour)

# Enable screenshots for debugging (WARNING: increases storage usage)
ENABLE_VERIFICATION_SCREENSHOTS = os.environ.get("ENABLE_VERIFICATION_SCREENSHOTS", "false").lower() == "true"

# ============================================================================
# OpenSERP Configuration (NEW)
# ============================================================================
# Enable OpenSERP with automatic crash recovery
# NOTE: Manager requires long-lived event loop (async web framework like FastAPI/Sanic)
# For demo scripts using asyncio.run(), start OpenSERP server manually:
#   cd /path/to/openserp && ./openserp serve -a 0.0.0.0 -p 7001 &
ENABLE_OPENSERP_MANAGER = os.environ.get("ENABLE_OPENSERP_MANAGER", "false").lower() == "true"
OPENSERP_BINARY_PATH = os.environ.get("OPENSERP_BINARY_PATH", "/Users/saksham/Codes/Google-Search-Test/openserp/openserp")
OPENSERP_MAX_RESTART_ATTEMPTS = int(os.environ.get("OPENSERP_MAX_RESTART_ATTEMPTS", "3"))
OPENSERP_HEALTH_CHECK_INTERVAL = float(os.environ.get("OPENSERP_HEALTH_CHECK_INTERVAL", "30.0"))

# ============================================================================
# Business Logic Configuration
# ============================================================================
RETAILER_ALLOWLIST = [
    # Primary retailers (preferred)
    "ASOS",
    "H&M",
    "Zara",
    "Macy's",
    "Amazon Fashion",
    "Urban Outfitters",
    "Revolve",

    # Fallback retailers (appear frequently in search results)
    "Nordstrom",
    "Bloomingdale's",
    "Target",
    "DSW",
    "Anthropologie",
    "JCPenney",
    "Saks Fifth Avenue",
    "Neiman Marcus"
]

MAX_ONLINE_ITEMS_PER_LOOK = 3

# Default budget caps (if not specified by user)
DEFAULT_SOFT_CAP = 150  # USD
DEFAULT_HARD_CAP = 300  # USD
