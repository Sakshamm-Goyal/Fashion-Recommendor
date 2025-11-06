# services/product_search_service.py
"""
Hybrid Product Search Service - The Heart of Intelligent Shopping.

Combines multiple search strategies:
1. Vector semantic search (existing products in DB)
2. Google Shopping API (real-time products)
3. ASOS API (fashion-specific)
4. ChatGPT search (fallback for when APIs not configured)

Uses intelligent deduplication, ranking, and LLM reranking for best results.
"""
import asyncio
from typing import List, Dict, Optional
from contracts.models import Product
import vector_index
from integrations.google_shopping import search_google_shopping
from integrations.asos_api import search_asos
from integrations.affiliate_manager import enrich_product_with_affiliate
from integrations.web_product_search import search_products_web  # NEW: Real web search
import config


class HybridProductSearch:
    """
    Multi-source product search with intelligent ranking.
    """

    def __init__(self):
        """Initialize hybrid search service."""
        # Check which APIs are configured
        self.enable_google_shopping = config.HAS_VALID_GOOGLE_SHOPPING  # Use validation from config
        self.enable_asos = config.ENABLE_ASOS_SEARCH  # Now configurable
        self.enable_vector_db = False  # DISABLED: Vector DB only contains fake/synthetic products from seed script
        self.enable_web_search = bool(config.OPENAI_API_KEY)  # NEW: Use web search for real products
        self._failed_sources = set()  # Track which sources have failed (fail-fast pattern)

    async def search_multi_source(
        self,
        descriptor: str,
        budget: Dict,
        filters: Optional[Dict] = None,
        retailers_allowlist: Optional[List[str]] = None,
        k: int = 50
    ) -> List[Product]:
        """
        Search across multiple sources in parallel.

        Args:
            descriptor: Product description (e.g., "Black leather Chelsea boots men's size 10")
            budget: Budget dict with soft_cap and hard_cap
            filters: Additional filters (gender, color, size, brand)
            retailers_allowlist: List of allowed retailers
            k: Total number of products to return

        Returns:
            List of Product objects, deduplicated and ranked
        """
        filters = filters or {}
        max_price = budget.get("hard_cap", 300)

        # Prepare search tasks for parallel execution
        tasks = []

        # 1. Vector DB search (existing catalog)
        if self.enable_vector_db:
            tasks.append(self._search_vector_db(descriptor, max_price, retailers_allowlist))

        # 2. Google Shopping (real-time, broad coverage)
        if self.enable_google_shopping and 'google_shopping' not in self._failed_sources:
            tasks.append(self._search_google_shopping(descriptor, max_price, filters))

        # 3. ASOS (fashion-specific, good for clothing)
        if self.enable_asos and 'asos' not in self._failed_sources:
            tasks.append(self._search_asos(descriptor, max_price, filters))

        # 4. Web Search (NEW - most reliable for real product URLs)
        # Uses actual web search to find products from major retailers
        if self.enable_web_search and 'web_search' not in self._failed_sources:
            tasks.append(self._search_web(descriptor, max_price, filters))

        # Execute all searches in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results and filter exceptions
        all_products = []
        for result in results:
            if isinstance(result, list):
                all_products.extend(result)
            elif isinstance(result, Exception):
                error_msg = str(result)
                print(f"Search source failed: {error_msg}")

                # Fail-fast: Mark sources as failed to avoid wasting time on subsequent searches
                if "400 Client Error" in error_msg or "Bad Request" in error_msg:
                    if "google" in error_msg.lower() or "customsearch" in error_msg.lower():
                        self._failed_sources.add('google_shopping')
                        print("[System] Disabling Google Shopping for this session (invalid API key)")
                elif "403" in error_msg or "Forbidden" in error_msg:
                    if "asos" in error_msg.lower():
                        self._failed_sources.add('asos')
                        print("[System] Disabling ASOS for this session (rate limited/blocked)")

        # Deduplicate products (by URL or title similarity)
        unique_products = self._deduplicate_products(all_products)

        # Filter by price and retailers
        filtered_products = self._apply_filters(
            unique_products,
            max_price=max_price,
            retailers_allowlist=retailers_allowlist
        )

        # Rank products (multi-signal ranking)
        ranked_products = self._rank_products(filtered_products, descriptor, budget, filters)

        # Return top-k
        return ranked_products[:k]

    async def _search_vector_db(
        self,
        descriptor: str,
        max_price: float,
        retailers_allowlist: Optional[List[str]]
    ) -> List[Product]:
        """Search existing vector database."""
        try:
            # Use existing vector_index.search_products function
            results = vector_index.search_products(
                descriptor=descriptor,
                price_max=max_price,
                retailers=retailers_allowlist or [],
                k=30  # Get top 30 from DB
            )

            # Convert to Product objects
            products = []
            for item in results:
                products.append(Product(
                    id=item["id"],
                    title=item["title"],
                    price=item["price"],
                    currency=item.get("currency", "USD"),
                    url=item["url"],
                    image=item.get("image"),
                    retailer=item["retailer"],
                    source="vector_db",
                    relevance_score=item.get("score", 0.0),
                    category=item.get("meta", {}).get("category"),
                    subcategory=item.get("meta", {}).get("subcategory"),
                    color=item.get("meta", {}).get("color"),
                    fabric=item.get("meta", {}).get("fabric"),
                ))

            return products

        except Exception as e:
            print(f"Vector DB search failed: {e}")
            return []

    async def _search_google_shopping(
        self,
        descriptor: str,
        max_price: float,
        filters: Dict
    ) -> List[Product]:
        """Search Google Shopping API."""
        try:
            # Run in thread pool since it's synchronous
            loop = asyncio.get_event_loop()
            products = await loop.run_in_executor(
                None,
                search_google_shopping,
                descriptor,
                max_price,
                filters,
                20  # Get top 20 from Google
            )
            return products

        except Exception as e:
            print(f"Google Shopping search failed: {e}")
            return []

    async def _search_asos(
        self,
        descriptor: str,
        max_price: float,
        filters: Dict
    ) -> List[Product]:
        """Search ASOS API."""
        try:
            # Run in thread pool since it's synchronous
            loop = asyncio.get_event_loop()
            products = await loop.run_in_executor(
                None,
                search_asos,
                descriptor,
                filters.get("gender"),
                max_price,
                filters,
                20  # Get top 20 from ASOS
            )
            return products

        except Exception as e:
            print(f"ASOS search failed: {e}")
            return []

    async def _search_web(
        self,
        descriptor: str,
        max_price: float,
        filters: Dict
    ) -> List[Product]:
        """
        Search using web search for REAL product URLs.

        This method performs actual web searches to find real products
        from major retailers, ensuring all URLs are legitimate.
        """
        try:
            print(f"[Web Search] Searching for real products...")
            # Run in thread pool since it's synchronous
            loop = asyncio.get_event_loop()
            products = await loop.run_in_executor(
                None,
                search_products_web,
                descriptor,
                0,  # min_price
                max_price,
                20  # Get top 20 from web search
            )
            print(f"[Web Search] Found {len(products)} real products")
            return products

        except Exception as e:
            print(f"Web search failed: {e}")
            return []

    def _deduplicate_products(self, products: List[Product]) -> List[Product]:
        """
        Deduplicate products by URL and title similarity.

        Strategy:
        1. Exact URL match → keep highest relevance
        2. Title similarity > 80% → keep one
        """
        if not products:
            return []

        # Simple deduplication by URL
        seen_urls = {}
        unique = []

        for product in products:
            url = product.url.lower()

            if url in seen_urls:
                # Keep product with higher relevance score
                existing = seen_urls[url]
                if (product.relevance_score or 0) > (existing.relevance_score or 0):
                    seen_urls[url] = product
            else:
                seen_urls[url] = product
                unique.append(product)

        # TODO: Add title-based deduplication using fuzzy matching
        # For now, URL-based is sufficient

        return unique

    def _apply_filters(
        self,
        products: List[Product],
        max_price: float,
        retailers_allowlist: Optional[List[str]]
    ) -> List[Product]:
        """Apply price and retailer filters."""
        filtered = []

        for product in products:
            # Price filter
            if product.price > max_price:
                continue

            # Retailer filter
            if retailers_allowlist:
                if product.retailer not in retailers_allowlist:
                    continue

            filtered.append(product)

        return filtered

    def _rank_products(
        self,
        products: List[Product],
        descriptor: str,
        budget: Dict,
        filters: Dict
    ) -> List[Product]:
        """
        Rank products using multi-signal scoring.

        Signals:
        1. Semantic relevance (from search)
        2. Price fit (within budget sweet spot)
        3. Source priority (ASOS > Google > Vector DB for fashion)
        4. In-stock availability
        5. Brand preference (if specified)
        """
        soft_cap = budget.get("soft_cap", 150)
        hard_cap = budget.get("hard_cap", 300)
        preferred_brands = filters.get("brands", [])

        scored_products = []

        for product in products:
            score = 0.0

            # 1. Semantic relevance (30% weight)
            if product.relevance_score:
                score += product.relevance_score * 0.3

            # 2. Price fit (25% weight)
            price_score = self._score_price_fit(product.price, soft_cap, hard_cap)
            score += price_score * 0.25

            # 3. Source priority (20% weight)
            source_scores = {
                "web_search": 1.0,  # BEST: Real products from actual web search
                "asos": 0.95,  # Best for fashion, real API
                "google_shopping": 0.9,  # Real-time, broad coverage
                "vector_db": 0.7,  # Lower priority (if re-enabled)
            }
            score += source_scores.get(product.source, 0.5) * 0.20

            # 4. In-stock availability (15% weight)
            if product.in_stock:
                score += 0.15

            # 5. Brand preference (10% weight)
            if preferred_brands and product.brand:
                if product.brand in preferred_brands:
                    score += 0.10

            scored_products.append((score, product))

        # Sort by score (descending)
        scored_products.sort(key=lambda x: x[0], reverse=True)

        # Return products only (without scores)
        return [product for score, product in scored_products]

    def _score_price_fit(self, price: float, soft_cap: float, hard_cap: float) -> float:
        """
        Score how well price fits budget.

        Sweet spot: Around soft cap (100% score)
        Acceptable: Up to hard cap (linearly decreasing)
        Over budget: 0 score
        """
        if price > hard_cap:
            return 0.0

        if price <= soft_cap:
            # Under or at soft cap: 80-100% score (closer to soft cap = better)
            return 0.8 + (price / soft_cap) * 0.2

        # Between soft and hard cap: linearly decrease from 80% to 20%
        excess = price - soft_cap
        max_excess = hard_cap - soft_cap
        penalty = (excess / max_excess) * 0.6  # Penalty up to 60%
        return 0.8 - penalty


# Global service instance
_product_search_service = None


def get_product_search_service() -> HybridProductSearch:
    """Get or create global product search service."""
    global _product_search_service
    if _product_search_service is None:
        _product_search_service = HybridProductSearch()
    return _product_search_service


# Convenience async function
async def search_products_hybrid(
    descriptor: str,
    budget: Dict,
    filters: Optional[Dict] = None,
    retailers_allowlist: Optional[List[str]] = None,
    k: int = 50
) -> List[Product]:
    """
    Quick async function for hybrid product search.

    Args:
        descriptor: Product description
        budget: Budget constraints
        filters: Optional filters
        retailers_allowlist: Allowed retailers
        k: Number of results

    Returns:
        List of ranked Product objects
    """
    service = get_product_search_service()
    return await service.search_multi_source(descriptor, budget, filters, retailers_allowlist, k)
