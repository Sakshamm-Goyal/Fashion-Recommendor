# integrations/google_shopping.py
"""
Google Shopping API integration for real-time product search.

Uses Google Custom Search JSON API with Shopping annotations.
Docs: https://developers.google.com/custom-search/v1/overview

Free Tier: 100 queries/day
Paid: $5 per 1000 queries after free tier
"""
import requests
from typing import List, Dict, Optional
import config
from contracts.models import Product


class GoogleShoppingClient:
    """
    Client for Google Shopping API (via Custom Search API).
    """

    def __init__(self, api_key: Optional[str] = None, cx: Optional[str] = None):
        """
        Initialize Google Shopping client.

        Args:
            api_key: Google API key (falls back to config.GOOGLE_SHOPPING_API_KEY)
            cx: Custom Search Engine ID (falls back to config.GOOGLE_SHOPPING_CX)
        """
        self.api_key = api_key or config.GOOGLE_SHOPPING_API_KEY
        self.cx = cx or config.GOOGLE_SHOPPING_CX
        self.base_url = "https://www.googleapis.com/customsearch/v1"

        if not self.api_key or not self.cx:
            raise ValueError(
                "Google Shopping API requires GOOGLE_SHOPPING_API_KEY and "
                "GOOGLE_SHOPPING_CX in environment/config"
            )

    def search_products(
        self,
        query: str,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        filters: Optional[Dict] = None,
        max_results: int = 10
    ) -> List[Product]:
        """
        Search for fashion products using Google Shopping.

        Args:
            query: Search query (e.g., "men's black leather boots size 10")
            max_price: Maximum price filter (in USD)
            min_price: Minimum price filter (in USD)
            filters: Additional filters (gender, brand, color, size)
            max_results: Number of results to return (max 10 per API call)

        Returns:
            List of Product objects with pricing and availability
        """
        filters = filters or {}

        # Build enhanced query with filters
        enhanced_query = query

        # Add filters to query (Google Shopping doesn't have structured filters in free API)
        if filters.get("gender"):
            enhanced_query += f" {filters['gender']}"
        if filters.get("brand"):
            enhanced_query += f" {filters['brand']}"
        if filters.get("color"):
            enhanced_query += f" {filters['color']}"
        if filters.get("size"):
            enhanced_query += f" size {filters['size']}"

        # Add price range if specified
        if min_price or max_price:
            if min_price and max_price:
                enhanced_query += f" ${min_price}-${max_price}"
            elif max_price:
                enhanced_query += f" under ${max_price}"

        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": enhanced_query,
            "num": min(max_results, 10),  # Max 10 per request
            "searchType": "image",  # Shopping results work better with image search
            "safe": "active",
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            products = []
            items = data.get("items", [])

            for idx, item in enumerate(items):
                # Extract product info from search result
                # Note: Free API has limited shopping data
                # For production, use Google Shopping Content API or Merchant Center

                product_id = f"google_shopping_{hash(item['link']) % 10000000}"

                # Extract price from snippet/title (best effort with free API)
                price = self._extract_price(item.get("snippet", ""), item.get("title", ""))

                # Get image
                image_url = None
                if "pagemap" in item and "cse_image" in item["pagemap"]:
                    image_url = item["pagemap"]["cse_image"][0].get("src")
                elif "image" in item:
                    image_url = item["image"].get("thumbnailLink")

                # Extract retailer from domain
                link = item.get("link", "")
                retailer = self._extract_retailer(link)

                products.append(Product(
                    id=product_id,
                    title=item.get("title", ""),
                    price=price,
                    currency="USD",
                    url=link,
                    image=image_url,
                    retailer=retailer,
                    source="google_shopping",
                    relevance_score=1.0 - (idx * 0.1),  # Decay by rank
                    in_stock=True,  # Assume true (free API doesn't provide)
                ))

            return products

        except requests.exceptions.RequestException as e:
            print(f"Google Shopping API error: {e}")
            return []
        except Exception as e:
            print(f"Error parsing Google Shopping results: {e}")
            return []

    def _extract_price(self, snippet: str, title: str) -> float:
        """
        Extract price from snippet or title using regex.
        This is a fallback for free API - production should use Shopping Content API.
        """
        import re

        text = f"{title} {snippet}"

        # Look for price patterns: $99.99, $99, 99.99, etc.
        price_patterns = [
            r'\$(\d+\.?\d*)',  # $99.99 or $99
            r'(\d+\.?\d*)\s*(?:USD|dollars?)',  # 99.99 USD
            r'Price:\s*\$?(\d+\.?\d*)',  # Price: $99.99
        ]

        for pattern in price_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return float(match.group(1))
                except (ValueError, IndexError):
                    continue

        # Default price if not found
        return 99.99

    def _extract_retailer(self, url: str) -> str:
        """Extract retailer name from URL domain."""
        from urllib.parse import urlparse

        try:
            domain = urlparse(url).netloc
            # Remove www. and .com
            retailer = domain.replace("www.", "").replace(".com", "").replace(".net", "")
            # Capitalize first letter
            return retailer.capitalize()
        except Exception:
            return "Unknown"


# Convenience function for quick searches
def search_google_shopping(
    query: str,
    max_price: Optional[float] = None,
    filters: Optional[Dict] = None,
    max_results: int = 10
) -> List[Product]:
    """
    Quick search function using Google Shopping API.

    Args:
        query: Search query
        max_price: Max price filter
        filters: Additional filters (gender, brand, color)
        max_results: Number of results

    Returns:
        List of Product objects
    """
    try:
        client = GoogleShoppingClient()
        return client.search_products(query, max_price=max_price, filters=filters, max_results=max_results)
    except ValueError as e:
        # API keys not configured, return empty
        print(f"Google Shopping not configured: {e}")
        return []
    except Exception as e:
        print(f"Google Shopping error: {e}")
        return []
