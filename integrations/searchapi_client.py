"""
SearchAPI.io Integration for Elara Fashion Recommendation System

This module provides access to Google Shopping and Google Search APIs via SearchAPI.io.
It serves as the PRIMARY product source for fashion recommendations.

Features:
- Google Shopping API for product search with advanced filtering
- Location-based targeting
- Price filtering and sorting
- Delivery time tracking
- Rating and review data
- Multi-retailer coverage

Author: Elara Team
"""

import asyncio
import httpx
from typing import List, Dict, Optional, Literal
from datetime import datetime
import re
import logging
from contracts.models import Product

logger = logging.getLogger(__name__)


class SearchAPIClient:
    """
    Client for SearchAPI.io Google Shopping and Search APIs.

    Primary product source for Elara fashion recommendations.
    Provides broad retailer coverage with rich product metadata.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://www.searchapi.io/api/v1/search",
        default_gl: str = "us",
        default_hl: str = "en",
        timeout: int = 30
    ):
        """
        Initialize SearchAPI client.

        Args:
            api_key: SearchAPI.io API key
            base_url: API endpoint URL
            default_gl: Default country code (us, uk, ca, etc.)
            default_hl: Default language code (en, es, fr, etc.)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = base_url
        self.default_gl = default_gl
        self.default_hl = default_hl
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        """Close httpx client"""
        await self._client.aclose()

    async def get_product_offers(
        self,
        product_id: str,
        gl: Optional[str] = None,
        hl: Optional[str] = None
    ) -> Dict:
        """
        Get merchant offers for a specific product to extract real merchant URLs.

        Args:
            product_id: Google Shopping product ID
            gl: Country code override
            hl: Language code override

        Returns:
            Dict containing sellers_results with direct merchant links
        """
        params = {
            "engine": "google_product",
            "product_id": product_id,
            "gl": gl or self.default_gl,
            "hl": hl or self.default_hl,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }

        try:
            response = await self._client.get(
                self.base_url,
                params=params,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            logger.info(
                f"SearchAPI product offers successful for product_id={product_id}: "
                f"found {len(data.get('sellers_results', {}).get('online_sellers', []))} sellers"
            )

            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"SearchAPI HTTP error {e.response.status_code}: {e.response.text}")
            return {}
        except asyncio.TimeoutError:
            logger.error(f"SearchAPI request timeout for product_id: {product_id}")
            return {}
        except Exception as e:
            logger.error(f"SearchAPI request failed: {str(e)}")
            return {}

    async def search_shopping(
        self,
        query: str,
        price_max: Optional[float] = None,
        price_min: Optional[float] = None,
        location: Optional[str] = None,
        sort_by: Optional[Literal["price_low_to_high", "price_high_to_low", "rating_high_to_low"]] = None,
        is_on_sale: Optional[bool] = None,
        is_free_delivery: Optional[bool] = None,
        condition: Optional[Literal["new", "used"]] = None,
        page: int = 1,
        gl: Optional[str] = None,
        hl: Optional[str] = None
    ) -> Dict:
        """
        Search Google Shopping for products.

        Args:
            query: Search query (supports embedded filters like "nike shoes under $100")
            price_max: Maximum price filter
            price_min: Minimum price filter
            location: Geographic location (e.g., "New York,United States", "California")
            sort_by: Sort order (price_low_to_high, price_high_to_low, rating_high_to_low)
            is_on_sale: Filter to sale items only
            is_free_delivery: Filter to free delivery only
            condition: Product condition (new or used)
            page: Page number for pagination
            gl: Country code override
            hl: Language code override

        Returns:
            Dict containing shopping_results, filters, metadata
        """
        params = {
            "engine": "google_shopping",
            "q": query,
            "gl": gl or self.default_gl,
            "hl": hl or self.default_hl,
            "page": page
        }

        # Add optional filters
        if price_max is not None:
            params["price_max"] = price_max
        if price_min is not None:
            params["price_min"] = price_min
        if location:
            params["location"] = location
        if sort_by:
            params["sort_by"] = sort_by
        if is_on_sale is not None:
            params["is_on_sale"] = str(is_on_sale).lower()
        if is_free_delivery is not None:
            params["is_free_delivery"] = str(is_free_delivery).lower()
        if condition:
            params["condition"] = condition

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }

        try:
            response = await self._client.get(
                self.base_url,
                params=params,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            logger.info(
                f"SearchAPI shopping search successful: {query[:50]}... "
                f"returned {len(data.get('shopping_results', []))} results"
            )

            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"SearchAPI HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except asyncio.TimeoutError:
            logger.error(f"SearchAPI request timeout for query: {query}")
            raise
        except Exception as e:
            logger.error(f"SearchAPI request failed: {str(e)}")
            raise

    async def search_products(
        self,
        descriptor: str,
        price_max: Optional[float] = None,
        location: Optional[str] = None,
        max_results: int = 10,
        prefer_new: bool = True,
        prefer_free_delivery: bool = False
    ) -> List[Product]:
        """
        Search for products and transform to Elara Product model with REAL merchant links.

        This is the main entry point for product search in Elara.
        For each product, it fetches merchant offers to get direct product URLs.

        Args:
            descriptor: Product description (e.g., "navy blazer", "white sneakers")
            price_max: Maximum price constraint
            location: User location for geo-targeting
            max_results: Maximum number of products to return
            prefer_new: Prefer new condition items
            prefer_free_delivery: Prefer items with free delivery

        Returns:
            List of Product objects with real merchant URLs
        """
        try:
            # Build search query with embedded price filter
            query = descriptor
            if price_max:
                query += f" under ${int(price_max)}"

            # Step 1: Execute initial shopping search
            logger.info(f"[SearchAPI] Searching Google Shopping for: {query}")
            data = await self.search_shopping(
                query=query,
                price_max=price_max,
                location=location,
                sort_by=None,  # Default sorting (relevance)
                condition="new" if prefer_new else None,
                is_free_delivery=prefer_free_delivery
            )

            shopping_results = data.get("shopping_results", [])
            if not shopping_results:
                logger.warning(f"[SearchAPI] No shopping results found for: {query}")
                return []

            logger.info(f"[SearchAPI] Found {len(shopping_results)} products, fetching merchant links...")

            # Step 2: For each product, fetch merchant offers to get real URLs
            products = []
            for idx, result in enumerate(shopping_results[:max_results * 2]):  # Fetch extra to account for filtering
                product_id = result.get("product_id")
                if not product_id:
                    logger.warning(f"[SearchAPI] Product {idx+1} has no product_id, skipping")
                    continue

                # Fetch merchant offers for this product
                offers_data = await self.get_product_offers(product_id)
                sellers = offers_data.get("sellers_results", {}).get("online_sellers", [])

                if not sellers:
                    logger.warning(f"[SearchAPI] No sellers found for product {product_id}")
                    continue

                # Extract products from each seller (each seller has a direct merchant link)
                for seller in sellers[:3]:  # Limit to top 3 sellers per product
                    product = self._seller_to_product(seller, result)
                    if product:
                        products.append(product)

                    # Stop if we have enough products
                    if len(products) >= max_results:
                        break

                if len(products) >= max_results:
                    break

            logger.info(f"[SearchAPI] Returning {len(products)} products with real merchant links")
            return products[:max_results]

        except Exception as e:
            logger.error(f"Product search failed for '{descriptor}': {type(e).__name__}: {str(e)}")
            logger.debug(f"Full error traceback:", exc_info=True)
            return []

    def _seller_to_product(
        self,
        seller: Dict,
        shopping_result: Dict
    ) -> Optional[Product]:
        """
        Convert a seller object (from product offers) to a Product object with real merchant URL.

        Args:
            seller: Seller object from sellers_results.online_sellers with link field
            shopping_result: Original shopping result with product details

        Returns:
            Product object with real merchant URL or None if conversion fails
        """
        try:
            # Extract direct merchant link
            merchant_link = seller.get("link")
            if not merchant_link:
                logger.warning(f"[SearchAPI] Seller has no link: {seller.get('name', 'Unknown')}")
                return None

            # Validate it's a real merchant URL (not Google redirect)
            if "google.com" in merchant_link or "shopping" in merchant_link:
                logger.warning(f"[SearchAPI] Seller link is Google redirect, skipping: {merchant_link[:100]}")
                return None

            # Extract retailer name
            retailer_name = seller.get("name", "Unknown")

            # Extract price
            price_str = seller.get("base_price", seller.get("total_price", seller.get("price", "$0")))
            price = self._parse_price(price_str)

            # Get product details from shopping_result
            title = shopping_result.get("title", "Unknown Product")
            thumbnail = shopping_result.get("thumbnail")

            # Extract brand from title (rough heuristic)
            brand = self._extract_brand(title)

            # Create Product object
            product = Product(
                id=f"searchapi_{shopping_result.get('product_id', '')}_{retailer_name.lower().replace(' ', '_')}",
                title=title,
                price=price,
                currency="USD",  # TODO: Parse from response
                url=merchant_link,  # REAL merchant URL!
                image=thumbnail or "",
                retailer=retailer_name,
                brand=brand,

                # Availability & Quality
                in_stock=True,  # Assume true for Google Shopping results
                shipping_days=self._parse_delivery_days(seller.get("delivery")),
                has_reviews=shopping_result.get("reviews") is not None,
                avg_rating=shopping_result.get("rating"),

                # Search metadata
                source="searchapi_shopping",
                relevance_score=0.9,  # High relevance since matched via Google Shopping

                # Additional fields
                condition=shopping_result.get("durability", "new").lower() if "durability" in shopping_result else "new",
                delivery_string=seller.get("delivery"),
                num_reviews=shopping_result.get("reviews"),
                discount_tag=shopping_result.get("tag")  # e.g., "14% OFF"
            )

            logger.info(f"[SearchAPI] Created product: {title[:50]}... from {retailer_name} -> {merchant_link[:80]}")
            return product

        except Exception as e:
            logger.error(f"[SearchAPI] Error converting seller to product: {e}")
            return None

    def _parse_price(self, price_str: str) -> float:
        """
        Parse price string like '$129.99' to float.

        Args:
            price_str: Price string from API

        Returns:
            Float price value
        """
        try:
            # Remove currency symbols and commas
            price_clean = price_str.replace("$", "").replace(",", "").strip()
            return float(price_clean)
        except (ValueError, AttributeError):
            logger.warning(f"[SearchAPI] Could not parse price: {price_str}")
            return 0.0

    def _transform_shopping_results(
        self,
        results: List[Dict],
        source: str = "searchapi_shopping"
    ) -> List[Product]:
        """
        Transform SearchAPI shopping results to Elara Product model.

        Args:
            results: List of shopping_results from API response
            source: Source identifier

        Returns:
            List of Product objects
        """
        products = []

        for idx, item in enumerate(results):
            try:
                product = Product(
                    id=f"searchapi_{item.get('product_id', idx)}",
                    title=item.get("title", ""),
                    price=item.get("extracted_price", 0.0),
                    currency="USD",  # TODO: Parse from response
                    url=item.get("product_link", ""),
                    image=item.get("thumbnail", ""),
                    retailer=item.get("seller", "Unknown"),
                    brand=self._extract_brand(item.get("title", "")),

                    # Availability & Quality
                    in_stock=True,  # Assume true for Google Shopping results
                    shipping_days=self._parse_delivery_days(item.get("delivery")),
                    has_reviews=item.get("reviews") is not None,
                    avg_rating=item.get("rating"),

                    # Search metadata
                    source=source,
                    relevance_score=1.0 - (idx * 0.05),  # Decay by position

                    # Additional fields from SearchAPI
                    condition=item.get("durability", "new").lower() if "durability" in item else "new",
                    delivery_string=item.get("delivery"),
                    num_reviews=item.get("reviews"),
                    original_price=item.get("extracted_original_price"),
                    discount_tag=item.get("tag")  # e.g., "14% OFF"
                )

                products.append(product)

            except Exception as e:
                logger.warning(f"Failed to transform product at index {idx}: {str(e)}")
                continue

        return products

    def _extract_brand(self, title: str) -> Optional[str]:
        """
        Extract brand name from product title.

        Args:
            title: Product title

        Returns:
            Brand name if found, None otherwise
        """
        # Common fashion brands (can be expanded)
        brands = [
            "Nike", "Adidas", "Puma", "Reebok", "Under Armour", "New Balance",
            "Zara", "H&M", "Forever 21", "ASOS", "Uniqlo", "Gap", "Old Navy",
            "Levi's", "Wrangler", "Lee", "Diesel",
            "Calvin Klein", "Tommy Hilfiger", "Ralph Lauren", "Polo",
            "Gucci", "Prada", "Dior", "Chanel", "Louis Vuitton", "Versace",
            "The North Face", "Patagonia", "Columbia",
            "J.Crew", "Banana Republic", "Madewell",
            "Nordstrom", "Macy's", "Target", "Kohl's",
            "Urban Outfitters", "Free People", "Anthropologie",
            "Vans", "Converse", "Dr. Martens", "Timberland", "Clarks"
        ]

        title_lower = title.lower()
        for brand in brands:
            if brand.lower() in title_lower:
                return brand

        return None

    def _parse_delivery_days(self, delivery_string: Optional[str]) -> Optional[int]:
        """
        Parse delivery string to number of days.

        Examples:
            "Free by 7/16" -> calculates days until 7/16
            "Ships in 2-3 days" -> returns 3
            "Free delivery" -> returns 6 (default estimate)

        Args:
            delivery_string: Delivery info from API

        Returns:
            Number of days, or None if cannot parse
        """
        if not delivery_string:
            return None

        delivery_lower = delivery_string.lower()

        # Pattern 1: "by MM/DD"
        match = re.search(r'by (\d{1,2})/(\d{1,2})', delivery_string)
        if match:
            try:
                month, day = int(match.group(1)), int(match.group(2))
                current_year = datetime.now().year

                # Handle year rollover
                target_date = datetime(current_year, month, day)
                if target_date < datetime.now():
                    target_date = datetime(current_year + 1, month, day)

                days = (target_date - datetime.now()).days
                return max(0, days)
            except ValueError:
                pass

        # Pattern 2: "in X-Y days" or "in X days"
        match = re.search(r'in (\d+)(?:-(\d+))? days?', delivery_lower)
        if match:
            min_days = int(match.group(1))
            max_days = int(match.group(2)) if match.group(2) else min_days
            return (min_days + max_days) // 2

        # Pattern 3: "X-Y business days"
        match = re.search(r'(\d+)(?:-(\d+))? business days?', delivery_lower)
        if match:
            min_days = int(match.group(1))
            max_days = int(match.group(2)) if match.group(2) else min_days
            return (min_days + max_days) // 2

        # Default estimates
        if "free" in delivery_lower or "delivery" in delivery_lower:
            return 6  # Default free delivery estimate

        return None

    async def search_with_filters(
        self,
        query: str,
        filters: Dict,
        max_results: int = 10
    ) -> List[Product]:
        """
        Advanced search with custom filter dictionary.

        Args:
            query: Search query
            filters: Dictionary of filters matching SearchAPI parameters
            max_results: Maximum results to return

        Returns:
            List of Product objects
        """
        try:
            data = await self.search_shopping(query=query, **filters)
            products = self._transform_shopping_results(
                data.get("shopping_results", []),
                source="searchapi_shopping"
            )
            return products[:max_results]
        except Exception as e:
            logger.error(f"Filtered search failed: {str(e)}")
            return []

    async def get_trending_products(
        self,
        category: str,
        location: Optional[str] = None,
        max_results: int = 20
    ) -> List[Product]:
        """
        Get trending products in a category.

        Args:
            category: Product category (e.g., "sneakers", "dresses", "jackets")
            location: Geographic location
            max_results: Maximum results

        Returns:
            List of trending Product objects
        """
        query = f"trending {category}"
        return await self.search_products(
            descriptor=query,
            location=location,
            max_results=max_results,
            prefer_new=True
        )


# Async context manager support
class SearchAPIClientContext(SearchAPIClient):
    """SearchAPI client with async context manager support"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Convenience function for one-off searches
async def quick_search(
    query: str,
    api_key: str,
    price_max: Optional[float] = None,
    location: Optional[str] = None,
    max_results: int = 10
) -> List[Product]:
    """
    Quick product search without managing client lifecycle.

    Args:
        query: Product search query
        api_key: SearchAPI.io API key
        price_max: Maximum price
        location: User location
        max_results: Max products to return

    Returns:
        List of Product objects
    """
    async with SearchAPIClientContext(api_key) as client:
        return await client.search_products(
            descriptor=query,
            price_max=price_max,
            location=location,
            max_results=max_results
        )
