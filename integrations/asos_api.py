# integrations/asos_api.py
"""
ASOS API integration for fashion product search.

ASOS doesn't have an official public API, but we can use their internal API
that powers their website. This is semi-public and used by their mobile apps.

Note: This is a gray area - for production, consider:
1. Contacting ASOS for official API access
2. Using ASOS affiliate program with proper attribution
3. Respecting rate limits and robots.txt
"""
import requests
from typing import List, Dict, Optional
import time
import re
from contracts.models import Product


class ASOSClient:
    """
    Client for ASOS product search using their internal API.
    """

    def __init__(self, country_code: str = "US", currency: str = "USD"):
        """
        Initialize ASOS client.

        Args:
            country_code: Country code (US, UK, etc.)
            currency: Currency code (USD, GBP, EUR)
        """
        self.country_code = country_code
        self.currency = currency
        self.base_url = "https://www.asos.com/api/product/search/v2/"

        # User agent to mimic browser (required)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # Rate limiting: 1 request per 2 seconds to be respectful
        self.last_request_time = 0
        self.min_request_interval = 2.0

        # Exponential backoff for 403 errors
        self.consecutive_403_errors = 0
        self.max_403_errors = 3  # After 3 consecutive 403s, back off significantly
        
        # Cache for keyStoreDataversion (fetched dynamically)
        self._key_store_dataversion: Optional[str] = None
        self._key_store_dataversion_cache_time: float = 0
        self._key_store_dataversion_cache_ttl: float = 3600  # Cache for 1 hour

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def _fetch_key_store_dataversion(self) -> Optional[str]:
        """
        Fetch the current keyStoreDataversion from ASOS homepage.
        
        This value is embedded in the HTML/JavaScript and changes periodically.
        We cache it for 1 hour to avoid fetching on every request.
        
        Returns:
            The keyStoreDataversion string, or None if not found
        """
        # Check cache first
        current_time = time.time()
        if (self._key_store_dataversion and 
            current_time - self._key_store_dataversion_cache_time < self._key_store_dataversion_cache_ttl):
            return self._key_store_dataversion
        
        try:
            # Fetch ASOS homepage to extract keyStoreDataversion
            homepage_url = f"https://www.asos.com/us/?country={self.country_code}"
            response = requests.get(
                homepage_url,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            html_content = response.text
            
            # Try to find keyStoreDataversion in various places
            # Pattern 1: Look for keyStoreDataversion in script tags or config
            patterns = [
                r'keyStoreDataversion["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                r'"keyStoreDataversion"\s*:\s*"([^"]+)"',
                r'keyStoreDataversion=([a-zA-Z0-9\-]+)',
                r'keystoredataversion["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    version = match.group(1)
                    # Cache it
                    self._key_store_dataversion = version
                    self._key_store_dataversion_cache_time = current_time
                    return version
            
            # If not found, try to find it in API response headers or make a test search
            # Sometimes it's in the response headers when making API calls
            return None
            
        except Exception as e:
            # Silently fail - we'll try without it or use a fallback
            return None
    
    def _get_key_store_dataversion(self) -> Optional[str]:
        """
        Get the keyStoreDataversion, fetching it if needed.
        
        Returns:
            The keyStoreDataversion string, or None if unavailable
        """
        version = self._fetch_key_store_dataversion()
        # If we can't fetch it, return None - the API might work without it
        # or we'll handle the error gracefully
        return version

    def search_products(
        self,
        query: str,
        gender: Optional[str] = None,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        filters: Optional[Dict] = None,
        max_results: int = 20
    ) -> List[Product]:
        """
        Search for products on ASOS.

        Args:
            query: Search query (e.g., "black leather boots")
            gender: Gender filter ("men", "women", "unisex")
            max_price: Maximum price
            min_price: Minimum price
            filters: Additional filters (color, size, brand)
            max_results: Number of results to return

        Returns:
            List of Product objects
        """
        self._rate_limit()

        # Check if we've hit too many 403 errors - back off gracefully
        if self.consecutive_403_errors >= self.max_403_errors:
            print(f"[ASOS] Skipping request - too many consecutive 403 errors ({self.consecutive_403_errors})")
            return []

        filters = filters or {}

        # Get the current keyStoreDataversion (fetched dynamically)
        key_store_dataversion = self._get_key_store_dataversion()

        # Build query parameters
        params = {
            "q": query,
            "store": "US",  # Store/country
            "currency": self.currency,
            "sizeSchema": "US",
            "limit": min(max_results, 72),  # ASOS API limit
            "offset": 0,
            "country": self.country_code,
            "lang": "en-US",
        }
        
        # Only add keyStoreDataversion if we have a valid one
        if key_store_dataversion:
            params["keyStoreDataversion"] = key_store_dataversion

        # Add gender filter (base_filter parameter)
        if gender:
            gender_map = {
                "men": "10584",  # Men's department ID
                "women": "1001",  # Women's department ID
            }
            if gender.lower() in gender_map:
                params["base_filter"] = f"department:{gender_map[gender.lower()]}"

        # Add price filters
        if min_price is not None or max_price is not None:
            price_filter = []
            if min_price is not None:
                price_filter.append(f"min:{int(min_price)}")
            if max_price is not None:
                price_filter.append(f"max:{int(max_price)}")
            params["price"] = ",".join(price_filter)

        try:
            response = requests.get(
                self.base_url,
                params=params,
                headers=self.headers,
                timeout=15  # Increased from 10 to 15 seconds
            )
            
            # Check for specific error about keyStoreDataversion (400 or 403)
            if response.status_code in (400, 403):
                try:
                    error_data = response.json()
                    # Error can be a list or a dict
                    error_list = error_data if isinstance(error_data, list) else [error_data]
                    
                    for error in error_list:
                        if (isinstance(error, dict) and 
                            "keystoredataversion" in error.get("parameterName", "").lower() and
                            ("invalid" in error.get("errorMessage", "").lower() or 
                             "invalid" in str(error).lower())):
                            # Invalid keyStoreDataversion - clear cache and retry without it
                            self._key_store_dataversion = None
                            self._key_store_dataversion_cache_time = 0
                            params.pop("keyStoreDataversion", None)
                            
                            # Retry the request without the parameter
                            response = requests.get(
                                self.base_url,
                                params=params,
                                headers=self.headers,
                                timeout=15
                            )
                            break
                except (ValueError, KeyError, TypeError):
                    pass  # Not JSON or doesn't match expected format

            response.raise_for_status()

            # Reset 403 error counter on success
            self.consecutive_403_errors = 0

            data = response.json()

            products = []
            items = data.get("products", [])

            for item in items[:max_results]:
                try:
                    product_id = str(item.get("id", ""))
                    name = item.get("name", "")
                    price_data = item.get("price", {})
                    price = price_data.get("current", {}).get("value", 0.0)

                    # Get primary image
                    image_url = None
                    if item.get("imageUrl"):
                        # ASOS uses template URLs with {size} placeholder
                        image_url = f"https://{item['imageUrl']}".replace("{size}", "xl")

                    # Build product URL
                    product_url = f"https://www.asos.com/us/prd/{product_id}"

                    # Check if product is in stock
                    in_stock = item.get("isInStock", True)

                    # Get brand
                    brand = item.get("brandName", "ASOS")

                    # Get color (from product variants)
                    color = None
                    if item.get("colour"):
                        color = item["colour"]

                    # Get available sizes
                    sizes = []
                    variants = item.get("variants", [])
                    for variant in variants:
                        if variant.get("isInStock") and variant.get("displaySizeText"):
                            sizes.append(variant["displaySizeText"])

                    products.append(Product(
                        id=f"asos_{product_id}",
                        title=name,
                        price=price,
                        currency=self.currency,
                        url=product_url,
                        image=image_url,
                        retailer="ASOS",
                        brand=brand,
                        color=color,
                        sizes_available=sizes,
                        in_stock=in_stock,
                        source="asos",
                        relevance_score=item.get("score", 0.0),  # ASOS provides relevance score
                    ))

                except Exception as e:
                    print(f"Error parsing ASOS product: {e}")
                    continue

            return products

        except requests.exceptions.Timeout:
            # Silent timeout - ASOS is slow or blocking us, but that's OK
            return []
        except requests.exceptions.RequestException as e:
            # Check for 403 Forbidden errors and track them
            if "403" in str(e) or "Forbidden" in str(e):
                self.consecutive_403_errors += 1
                print(f"ASOS API 403 error ({self.consecutive_403_errors}/{self.max_403_errors}): {e}")

                if self.consecutive_403_errors >= self.max_403_errors:
                    print(f"[ASOS] Rate limited - backing off for this session")
            else:
                # Log other network errors but don't be noisy
                if "Read timed out" not in str(e):  # Avoid duplicate timeout messages
                    print(f"ASOS API error: {e}")
            return []
        except Exception as e:
            print(f"Error parsing ASOS results: {e}")
            return []


# Convenience function for quick searches
def search_asos(
    query: str,
    gender: Optional[str] = None,
    max_price: Optional[float] = None,
    filters: Optional[Dict] = None,
    max_results: int = 20
) -> List[Product]:
    """
    Quick search function for ASOS products.

    Args:
        query: Search query
        gender: Gender filter ("men", "women")
        max_price: Maximum price
        filters: Additional filters
        max_results: Number of results

    Returns:
        List of Product objects
    """
    try:
        client = ASOSClient()
        return client.search_products(
            query,
            gender=gender,
            max_price=max_price,
            filters=filters,
            max_results=max_results
        )
    except Exception as e:
        print(f"ASOS search error: {e}")
        return []
