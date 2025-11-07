# integrations/retailed_client.py
"""
Retailed.io API Integration for Elara AI Personal Stylist.

COMPLEMENTARY product source for retailer-specific scraping.
Supports: Nike, Zara, Forever21, Uniqlo, Dior, Farfetch, Macy's,
         Zalando, StockX, Goat, Stadium Goods

Used when:
- User requests specific retailer
- Need rich metadata (sizes, variants, reviews)
- SearchAPI results insufficient

Credit-based system - use sparingly and track budget.
"""
import httpx
from typing import List, Dict, Optional, Literal
from contracts.models import Product
import config


class RetailedClient:
    """
    Retailed.io API client for retailer-specific product scraping.

    Architecture:
    - Credit-based API (track usage)
    - Retailer-specific endpoints
    - Rich metadata extraction
    - Complementary to SearchAPI.io (not primary)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://app.retailed.io/api/v1/scraper",
        timeout: int = 30,
    ):
        """
        Initialize Retailed.io client.

        Args:
            api_key: Retailed.io API key
            base_url: Base URL for Retailed.io API
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.session = httpx.AsyncClient(timeout=timeout)

        # Credit tracking
        self.credits_used = 0
        self.credits_remaining = None

    async def search_retailer(
        self,
        retailer: str,
        query: str,
        max_results: int = 10,
        price_max: Optional[float] = None,
        sort_by: Optional[Literal["price_low_to_high", "price_high_to_low", "relevance"]] = None,
    ) -> List[Product]:
        """
        Search a specific retailer via Retailed.io.

        Args:
            retailer: Retailer name (e.g., "nike", "zara", "stockx")
            query: Search query
            max_results: Maximum number of results
            price_max: Maximum price filter
            sort_by: Sort order

        Returns:
            List of Product objects

        Raises:
            ValueError: If retailer not supported
            httpx.HTTPError: If API request fails
        """
        # Validate retailer
        retailer_lower = retailer.lower()
        if retailer_lower not in config.RETAILED_SUPPORTED_RETAILERS:
            raise ValueError(
                f"Retailer '{retailer}' not supported. "
                f"Supported: {', '.join(config.RETAILED_SUPPORTED_RETAILERS)}"
            )

        # Check credit budget
        if self.credits_used >= config.RETAILED_MAX_REQUESTS_PER_SESSION:
            print(f"[Retailed.io] Credit budget exceeded ({self.credits_used} requests)")
            return []

        # Build request
        endpoint = f"{self.base_url}/{retailer_lower}/search"
        params = {
            "q": query,
            "limit": max_results,
        }

        if price_max:
            params["price_max"] = price_max

        if sort_by:
            params["sort"] = sort_by

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = await self.session.get(endpoint, params=params, headers=headers)
            response.raise_for_status()

            data = response.json()

            # Track credits
            self.credits_used += 1
            self.credits_remaining = response.headers.get("X-Credits-Remaining")

            if self.credits_remaining and int(self.credits_remaining) < config.RETAILED_CREDIT_WARNING_THRESHOLD:
                print(f"[Retailed.io] Warning: Only {self.credits_remaining} credits remaining")

            # Parse products
            products = self._parse_response(data, retailer)

            return products[:max_results]

        except httpx.HTTPStatusError as e:
            print(f"[Retailed.io] HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            print(f"[Retailed.io] Search failed: {e}")
            raise

    async def get_product_details(
        self,
        retailer: str,
        product_url: str
    ) -> Optional[Product]:
        """
        Get detailed product information from a specific URL.

        Args:
            retailer: Retailer name
            product_url: Product page URL

        Returns:
            Product object with detailed metadata
        """
        retailer_lower = retailer.lower()
        if retailer_lower not in config.RETAILED_SUPPORTED_RETAILERS:
            raise ValueError(f"Retailer '{retailer}' not supported")

        # Check credit budget
        if self.credits_used >= config.RETAILED_MAX_REQUESTS_PER_SESSION:
            print(f"[Retailed.io] Credit budget exceeded")
            return None

        endpoint = f"{self.base_url}/{retailer_lower}/product"
        params = {"url": product_url}
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            response = await self.session.get(endpoint, params=params, headers=headers)
            response.raise_for_status()

            data = response.json()
            self.credits_used += 1

            return self._parse_product_details(data, retailer)

        except Exception as e:
            print(f"[Retailed.io] Product details fetch failed: {e}")
            return None

    def _parse_response(self, data: Dict, retailer: str) -> List[Product]:
        """
        Parse Retailed.io search response.

        Expected structure:
        {
            "results": [
                {
                    "title": "Product Title",
                    "price": 99.99,
                    "currency": "USD",
                    "url": "https://...",
                    "image": "https://...",
                    "brand": "Nike",
                    "sizes": ["S", "M", "L"],
                    "colors": ["Black", "White"],
                    "rating": 4.5,
                    "reviews": 123,
                    "in_stock": true
                }
            ]
        }
        """
        products = []

        results = data.get("results", [])

        for item in results:
            try:
                product = Product(
                    id=f"retailed_{retailer}_{item.get('id', item.get('url', '').split('/')[-1])}",
                    title=item.get("title", ""),
                    price=float(item.get("price", 0)),
                    currency=item.get("currency", "USD"),
                    url=item.get("url", ""),
                    image=item.get("image"),
                    retailer=retailer.title(),
                    brand=item.get("brand"),
                    category=item.get("category"),
                    subcategory=item.get("subcategory"),
                    color=item.get("color"),
                    fabric=item.get("fabric") or item.get("material"),
                    sizes_available=item.get("sizes", []),
                    in_stock=item.get("in_stock", True),
                    rating=item.get("rating"),
                    review_count=item.get("reviews") or item.get("review_count"),
                    source="retailed_io",
                    condition=item.get("condition", "new"),
                    availability_status=self._parse_availability(item),
                )

                products.append(product)

            except Exception as e:
                print(f"[Retailed.io] Failed to parse product: {e}")
                continue

        return products

    def _parse_product_details(self, data: Dict, retailer: str) -> Product:
        """Parse detailed product response."""
        return Product(
            id=f"retailed_{retailer}_{data.get('id', '')}",
            title=data.get("title", ""),
            price=float(data.get("price", 0)),
            currency=data.get("currency", "USD"),
            url=data.get("url", ""),
            image=data.get("image"),
            retailer=retailer.title(),
            brand=data.get("brand"),
            category=data.get("category"),
            subcategory=data.get("subcategory"),
            color=data.get("color"),
            fabric=data.get("fabric") or data.get("material"),
            sizes_available=data.get("sizes", []),
            in_stock=data.get("in_stock", True),
            rating=data.get("rating"),
            review_count=data.get("reviews") or data.get("review_count"),
            source="retailed_io",
            condition=data.get("condition", "new"),
            availability_status=self._parse_availability(data),
            fit_type=self._parse_fit_type(data),
        )

    def _parse_availability(self, item: Dict) -> Literal["in_stock", "low_stock", "backorder", "out_of_stock"]:
        """Parse availability status from item data."""
        in_stock = item.get("in_stock", True)
        stock_level = item.get("stock_level", "")

        if not in_stock:
            return "out_of_stock"
        elif "low" in stock_level.lower():
            return "low_stock"
        elif "backorder" in stock_level.lower() or "pre-order" in stock_level.lower():
            return "backorder"
        else:
            return "in_stock"

    def _parse_fit_type(self, item: Dict) -> Optional[Literal["slim", "regular", "relaxed", "oversized"]]:
        """Parse fit type from item data."""
        fit_str = item.get("fit", "").lower()
        title = item.get("title", "").lower()

        combined = f"{fit_str} {title}"

        if any(kw in combined for kw in ["slim", "fitted", "skinny"]):
            return "slim"
        elif any(kw in combined for kw in ["relaxed", "loose", "comfort"]):
            return "relaxed"
        elif any(kw in combined for kw in ["oversized", "baggy", "boyfriend"]):
            return "oversized"
        elif "regular" in combined or "classic" in combined:
            return "regular"

        return None

    async def search_products(
        self,
        descriptor: str,
        preferred_retailers: Optional[List[str]] = None,
        price_max: Optional[float] = None,
        max_results: int = 10,
    ) -> List[Product]:
        """
        Smart search across multiple retailers based on descriptor.

        Args:
            descriptor: Product description
            preferred_retailers: List of preferred retailers to search
            price_max: Maximum price
            max_results: Maximum results per retailer

        Returns:
            List of products from all searched retailers
        """
        if not preferred_retailers:
            # Auto-detect retailers from descriptor
            preferred_retailers = self._detect_retailers(descriptor)

        products = []

        for retailer in preferred_retailers[:3]:  # Limit to 3 retailers to save credits
            try:
                retailer_products = await self.search_retailer(
                    retailer=retailer,
                    query=descriptor,
                    max_results=max_results,
                    price_max=price_max,
                )
                products.extend(retailer_products)

            except Exception as e:
                print(f"[Retailed.io] Failed to search {retailer}: {e}")
                continue

        return products

    def _detect_retailers(self, descriptor: str) -> List[str]:
        """
        Detect relevant retailers from product descriptor.

        Args:
            descriptor: Product description

        Returns:
            List of retailer names
        """
        descriptor_lower = descriptor.lower()
        retailers = []

        # Sneaker/Streetwear retailers
        if any(kw in descriptor_lower for kw in ["sneakers", "jordans", "yeezy", "dunk", "streetwear"]):
            retailers.extend(["stockx", "goat", "stadium goods", "nike"])

        # Fast fashion retailers
        if any(kw in descriptor_lower for kw in ["trendy", "affordable", "fast fashion"]):
            retailers.extend(["zara", "forever21", "uniqlo"])

        # Luxury retailers
        if any(kw in descriptor_lower for kw in ["luxury", "designer", "high-end"]):
            retailers.extend(["farfetch", "dior"])

        # Department stores
        if any(kw in descriptor_lower for kw in ["classic", "versatile", "everyday"]):
            retailers.extend(["macys", "zalando"])

        # Default to popular general retailers
        if not retailers:
            retailers = ["zara", "nike", "uniqlo"]

        return retailers[:3]  # Limit to 3 to save credits

    async def close(self):
        """Close the HTTP session."""
        await self.session.aclose()

    def get_credit_usage(self) -> Dict[str, any]:
        """
        Get credit usage statistics.

        Returns:
            Dictionary with credit usage info
        """
        return {
            "credits_used": self.credits_used,
            "credits_remaining": self.credits_remaining,
            "max_per_session": config.RETAILED_MAX_REQUESTS_PER_SESSION,
            "warning_threshold": config.RETAILED_CREDIT_WARNING_THRESHOLD,
        }
