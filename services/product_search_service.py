# services/product_search_service.py
"""
Hybrid Product Search Service - The Heart of Intelligent Shopping.

Combines multiple search strategies:
1. OpenSERP (PRIMARY - Local Google/Bing/DuckDuckGo scraper, NO API costs, runs on port 7001)
2. Visual Scraping (FALLBACK - Playwright + Claude Vision for when selectors fail)
3. ASOS API (fashion-specific with DIRECT URLs)
4. Retailed.io (DISABLED - API returning 500 errors)
5. Vector semantic search (existing products in DB - currently disabled)

OpenSERP Benefits:
- FREE - No API costs
- FAST - Local server, no network latency
- RELIABLE - Scrapes Google Shopping, Bing, DuckDuckGo simultaneously
- WORKING - Tested and verified with real results

Visual Scraping Fallback:
- Uses Playwright + Claude Vision to extract products from screenshots
- More robust against HTML structure changes
- Slower but works when traditional selectors fail

Uses intelligent deduplication, ranking, and LLM reranking for best results.
"""
import asyncio
from typing import List, Dict, Optional
from contracts.models import Product
import vector_index
from integrations.google_shopping import search_google_shopping
from integrations.asos_api import search_asos
from integrations.affiliate_manager import enrich_product_with_affiliate
from integrations.searchapi_client import SearchAPIClient  # DEPRECATED: Replaced by Oxylabs
from integrations.oxylabs_client import OxylabsClient  # PRIMARY: Google Shopping via Oxylabs
from integrations.retailed_client import RetailedClient  # DISABLED: API returning 500 errors

# PRIMARY: OpenSERP (local scraper, no API costs)
from integrations.openserp_client import OpenSERPClient, ProductCandidate as OpenSERPCandidate
from integrations.openserp_manager import OpenSERPManager

# FALLBACK: Claude web search (Anthropic API with web search)
from integrations.claude_web_search import ClaudeWebSearchClient, ProductCandidate as ClaudeCandidate

# FALLBACK: Visual scraping (Playwright + Claude Vision) - DISABLED
from integrations.visual_shopping_scraper import VisualShoppingScraper, ProductCandidate as VisualCandidate

# Multi-stage filtering pipeline (LEGACY - replaced by OpenSERP)
from integrations.google_shopping_harvester import GoogleShoppingHarvester, ProductCandidate
from services.http_prefilter import HTTPPreFilter, ProductDetails
from services.retailer_api_connectors import RetailerAPIConnectors, VariantDetails
from services.playwright_product_verifier import PlaywrightProductVerifier, VerifiedProduct
from services.link_hardening import LinkHardener, HardenedLink

from services.link_verification_agent import LinkVerificationAgent  # LEGACY link verification
from services.link_cache import LinkVerificationCache  # Caching layer
import config


class HybridProductSearch:
    """
    Multi-source product search with intelligent ranking.
    """

    def __init__(self):
        """Initialize hybrid search service."""
        # Check which APIs are configured
        self.enable_openserp = False  # PRIMARY: Local scraper on port 7001 (TEMP DISABLED - using Claude web search instead)
        self.enable_visual_scraping = False  # DISABLED: Chromium gets CAPTCHA'd, not working
        self.enable_asos = config.ENABLE_ASOS_SEARCH  # Returns direct URLs (but has 403 errors)
        self.enable_retailed = config.ENABLE_RETAILED  # DISABLED: API returning 500 errors
        self.enable_oxylabs = config.ENABLE_OXYLABS  # PRIMARY: Oxylabs for Google Shopping (replaces SearchAPI)
        self.enable_searchapi = config.ENABLE_SEARCHAPI  # DEPRECATED: Use Oxylabs instead (rate limited)
        self.enable_google_shopping = False  # DISABLED: CAPTCHA issues with Chromium scraper
        self.enable_vector_db = False  # DISABLED: Vector DB only contains fake/synthetic products from seed script
        self._failed_sources = set()  # Track which sources have failed (fail-fast pattern)

        # Initialize OpenSERP with managed server (PRIMARY - local scraper with auto-restart)
        if self.enable_openserp:
            self.openserp_client = OpenSERPClient(base_url="http://localhost:7001")

            # Initialize OpenSERP manager for automatic crash recovery (if enabled)
            if config.ENABLE_OPENSERP_MANAGER:
                self.openserp_manager = OpenSERPManager(
                    openserp_binary_path=config.OPENSERP_BINARY_PATH,
                    host="0.0.0.0",
                    port=7001,
                    max_restart_attempts=config.OPENSERP_MAX_RESTART_ATTEMPTS,
                    health_check_interval=config.OPENSERP_HEALTH_CHECK_INTERVAL
                )
                print("[ProductSearch] OpenSERP manager initialized (auto-restart enabled)")
            else:
                self.openserp_manager = None
                print("[ProductSearch] OpenSERP manager disabled (manual server management)")

            print("[ProductSearch] OpenSERP client initialized (port 7001)")
        else:
            self.openserp_client = None
            self.openserp_manager = None

        # Initialize Claude Web Search (FALLBACK for better product URLs)
        if config.ENABLE_CLAUDE_WEB_SEARCH:
            try:
                self.claude_web_search_client = ClaudeWebSearchClient()
                print("[ProductSearch] Claude web search initialized (Anthropic API)")
            except ValueError as e:
                print(f"[ProductSearch] Claude web search disabled: {e}")
                self.claude_web_search_client = None
        else:
            self.claude_web_search_client = None

        # Initialize Visual Scraping (FALLBACK)
        if self.enable_visual_scraping:
            try:
                self.visual_scraper = VisualShoppingScraper()
                print("[ProductSearch] Visual scraper initialized (Claude Vision)")
            except ValueError as e:
                print(f"[ProductSearch] Visual scraper disabled: {e}")
                self.visual_scraper = None
                self.enable_visual_scraping = False
        else:
            self.visual_scraper = None

        # Initialize Oxylabs client (PRIMARY - Google Shopping)
        if self.enable_oxylabs:
            self.oxylabs_client = OxylabsClient(
                username=config.OXYLABS_USERNAME,
                password=config.OXYLABS_PASSWORD
            )
            print("[ProductSearch] Oxylabs client initialized (Google Shopping)")
        else:
            self.oxylabs_client = None

        # Initialize SearchAPI client (DEPRECATED - replaced by Oxylabs)
        if self.enable_searchapi:
            self.searchapi_client = SearchAPIClient(
                api_key=config.SEARCHAPI_KEY,
                base_url=config.SEARCHAPI_BASE_URL,
                default_gl=config.SEARCHAPI_DEFAULT_GL,
                default_hl=config.SEARCHAPI_DEFAULT_HL
            )
        else:
            self.searchapi_client = None

        # Initialize Retailed.io client
        if self.enable_retailed:
            self.retailed_client = RetailedClient(
                api_key=config.RETAILED_API_KEY,
                base_url=config.RETAILED_BASE_URL
            )
        else:
            self.retailed_client = None

        # Initialize link verification agent (with browser pool for parallel verification)
        self.enable_link_verification = config.ENABLE_LINK_VERIFICATION
        if self.enable_link_verification:
            self.verification_agent = LinkVerificationAgent(
                concurrency=config.VERIFICATION_CONCURRENCY,
                timeout=config.VERIFICATION_TIMEOUT,
                enable_screenshots=config.ENABLE_VERIFICATION_SCREENSHOTS,
                max_retries=2
            )
            # Initialize cache
            self.verification_cache = LinkVerificationCache(
                redis_url=config.REDIS_URL,
                default_ttl=config.VERIFICATION_CACHE_TTL
            )
        else:
            self.verification_agent = None
            self.verification_cache = None

    async def start(self):
        """
        Start the product search service and OpenSERP manager (if enabled).
        Should be called once at application startup.
        """
        if self.openserp_manager:
            print("[ProductSearch] Starting OpenSERP manager...")
            success = await self.openserp_manager.start()
            if success:
                print("[ProductSearch] ✓ OpenSERP manager started successfully")
            else:
                print("[ProductSearch] ✗ Failed to start OpenSERP manager")
                print("[ProductSearch] Product search will attempt to use existing OpenSERP server")

    async def stop(self):
        """
        Stop the product search service and OpenSERP manager (if enabled).
        Should be called at application shutdown.
        """
        if self.openserp_manager:
            print("[ProductSearch] Stopping OpenSERP manager...")
            await self.openserp_manager.stop()
            print("[ProductSearch] ✓ OpenSERP manager stopped")

    async def check_health(self) -> Dict[str, bool]:
        """
        Check health of all search sources.

        Returns:
            Dict mapping source name to health status (True=healthy, False=unhealthy)
        """
        health = {}

        # Check OpenSERP
        if self.openserp_client:
            try:
                healthy = await self.openserp_client.check_health()
                health['openserp'] = healthy
            except Exception as e:
                print(f"[ProductSearch] OpenSERP health check error: {e}")
                health['openserp'] = False

        # Check Claude web search
        if self.claude_web_search_client:
            health['claude_web_search'] = True  # Always healthy (external API)

        # Check ASOS
        if self.enable_asos:
            health['asos'] = True  # Always healthy (external API)

        return health

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

        # 1. OpenSERP (PRIMARY - local Google/Bing/DuckDuckGo scraper, FREE, NO API costs)
        if self.enable_openserp and 'openserp' not in self._failed_sources:
            tasks.append(self._search_openserp(descriptor, max_price))

        # 2. Claude Web Search (FALLBACK - uses Claude's web search for verified product URLs)
        if self.claude_web_search_client and 'claude_web_search' not in self._failed_sources:
            tasks.append(self._search_claude_web(descriptor, max_price, retailers_allowlist))

        # 3. Visual Scraping (FALLBACK - Playwright + Claude Vision, slower but robust)
        # Only use if OpenSERP fails or returns few results
        if self.enable_visual_scraping and 'visual_scraping' not in self._failed_sources:
            tasks.append(self._search_visual(descriptor, max_price))

        # 3. ASOS (fashion-specific, good for clothing diversity)
        if self.enable_asos and 'asos' not in self._failed_sources:
            tasks.append(self._search_asos(descriptor, max_price, filters))

        # 4. Oxylabs Google Shopping (PRIMARY - replaces SearchAPI)
        if self.enable_oxylabs and 'oxylabs' not in self._failed_sources:
            location = filters.get("location") if filters else None
            tasks.append(self._search_oxylabs(descriptor, max_price, location))

        # 4b. SearchAPI.io Google Shopping (DEPRECATED - replaced by Oxylabs)
        elif self.enable_searchapi and 'searchapi' not in self._failed_sources:
            location = filters.get("location") if filters else None
            tasks.append(self._search_searchapi(descriptor, max_price, location))

        # 5. Retailed.io (DISABLED - API returning 500 errors)
        if self.enable_retailed and 'retailed' not in self._failed_sources:
            preferred_retailers = filters.get("preferred_retailers") if filters else None
            tasks.append(self._search_retailed(descriptor, max_price, preferred_retailers))

        # 6. Vector DB search (existing catalog) - DISABLED
        if self.enable_vector_db:
            tasks.append(self._search_vector_db(descriptor, max_price, retailers_allowlist))

        # 7. Google Shopping (LEGACY)
        if self.enable_google_shopping and 'google_shopping' not in self._failed_sources:
            tasks.append(self._search_google_shopping(descriptor, max_price, filters))

        # Execute all searches in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        print(f"[DEBUG] search_multi_source: {len(results)} results from asyncio.gather")

        # Flatten results and filter exceptions
        all_products = []
        for i, result in enumerate(results):
            if isinstance(result, list):
                print(f"[DEBUG] Result {i}: {len(result)} products")
                all_products.extend(result)
            elif isinstance(result, Exception):
                error_msg = str(result)
                print(f"[DEBUG] Result {i}: Exception - {error_msg}")
                print(f"Search source failed: {error_msg}")

                # Fail-fast: Mark sources as failed to avoid wasting time on subsequent searches
                if "400 Client Error" in error_msg or "Bad Request" in error_msg:
                    if "oxylabs" in error_msg.lower():
                        self._failed_sources.add('oxylabs')
                        print("[System] Disabling Oxylabs for this session (invalid credentials)")
                    elif "searchapi" in error_msg.lower():
                        self._failed_sources.add('searchapi')
                        print("[System] Disabling SearchAPI for this session (invalid API key)")
                    elif "retailed" in error_msg.lower():
                        self._failed_sources.add('retailed')
                        print("[System] Disabling Retailed.io for this session (invalid API key)")
                    elif "google" in error_msg.lower() or "customsearch" in error_msg.lower():
                        self._failed_sources.add('google_shopping')
                        print("[System] Disabling Google Shopping for this session (invalid API key)")
                elif "403" in error_msg or "Forbidden" in error_msg:
                    if "oxylabs" in error_msg.lower():
                        self._failed_sources.add('oxylabs')
                        print("[System] Disabling Oxylabs for this session (rate limited/blocked)")
                    elif "asos" in error_msg.lower():
                        self._failed_sources.add('asos')
                        print("[System] Disabling ASOS for this session (rate limited/blocked)")
                    elif "retailed" in error_msg.lower():
                        self._failed_sources.add('retailed')
                        print("[System] Disabling Retailed.io for this session (credit limit reached)")
                elif "401" in error_msg or "Unauthorized" in error_msg:
                    if "oxylabs" in error_msg.lower():
                        self._failed_sources.add('oxylabs')
                        print("[System] Disabling Oxylabs for this session (invalid credentials)")
                    elif "searchapi" in error_msg.lower():
                        self._failed_sources.add('searchapi')
                        print("[System] Disabling SearchAPI for this session (unauthorized)")
                    elif "retailed" in error_msg.lower():
                        self._failed_sources.add('retailed')
                        print("[System] Disabling Retailed.io for this session (unauthorized)")

        # STEP 1: Link Verification (ensures 95-100% working links)
        if self.enable_link_verification and all_products:
            print(f"\n[Link Verification] Verifying {len(all_products)} products...")

            # Check cache first
            if self.verification_cache and self.verification_cache._client:
                urls = [p.url for p in all_products]
                cached_products_dict = await self.verification_cache.get_batch(urls)

                if cached_products_dict:
                    print(f"[Cache] Found {len(cached_products_dict)} cached verifications")

                    # Separate cached vs uncached
                    cached_products = list(cached_products_dict.values())
                    uncached_products = [
                        p for p in all_products
                        if p.url not in cached_products_dict
                    ]
                else:
                    cached_products = []
                    uncached_products = all_products
            else:
                cached_products = []
                uncached_products = all_products

            # Verify uncached products (limit to top 30 by relevance to save time)
            if uncached_products:
                uncached_products.sort(
                    key=lambda p: p.relevance_score or 0.0,
                    reverse=True
                )
                products_to_verify = uncached_products[:30]

                print(f"[Verification] Checking {len(products_to_verify)} products in real-time...")

                # Use browser pool for parallel verification (15 concurrent contexts)
                verified_products, verification_results = await self.verification_agent.batch_verify_products(
                    products_to_verify
                )

                print(f"[Verification] {len(verified_products)}/{len(products_to_verify)} products verified")

                # Cache successful verifications
                if self.verification_cache and verified_products:
                    await self.verification_cache.cache_batch(verified_products)

                # Combine cached + newly verified
                all_products = cached_products + verified_products
            else:
                all_products = cached_products

            if not all_products:
                print("[Warning] No products passed verification - falling back to unverified results")
                all_products = uncached_products[:k]  # Return top k unverified as fallback

        print(f"[DEBUG] Before deduplication: {len(all_products)} products")

        # Deduplicate products (by URL or title similarity)
        unique_products = self._deduplicate_products(all_products)
        print(f"[DEBUG] After deduplication: {len(unique_products)} products")

        # Filter by price and retailers
        filtered_products = self._apply_filters(
            unique_products,
            max_price=max_price,
            retailers_allowlist=retailers_allowlist
        )
        print(f"[DEBUG] After filtering (max_price={max_price}, retailers={retailers_allowlist}): {len(filtered_products)} products")

        # Rank products (multi-signal ranking)
        ranked_products = self._rank_products(filtered_products, descriptor, budget, filters)
        print(f"[DEBUG] After ranking: {len(ranked_products)} products, returning top {k}")

        # Return top-k
        return ranked_products[:k]

    async def _search_custom_pipeline(
        self,
        descriptor: str,
        max_price: float,
        filters: Dict
    ) -> List[Product]:
        """
        Custom Multi-Stage Scraping Pipeline (PRIMARY SOURCE).

        5-Stage Filtering:
        - Stage A: Google Shopping harvester (Selenium) → ~20 candidates
        - Stage B: HTTP pre-filter (JSON-LD) → ~5-10 candidates
        - Stage C: Retailer API connectors (Shopify) → API-verified products
        - Stage D: Playwright verifier (variant + ZIP + ETA) → Browser-verified
        - Stage E: Link hardening (validation) → 100% working links

        Target: 95-100% link accuracy.
        """
        try:
            print(f"[Custom Pipeline] Starting multi-stage filtering for: {descriptor[:50]}...")

            # STAGE A: Harvest candidates from Google Shopping
            print(f"[Stage A] Harvesting from Google Shopping...")
            candidates: List[ProductCandidate] = await self.harvester.harvest(
                query=descriptor,
                max_price=max_price
            )

            if not candidates:
                print("[Stage A] No candidates found")
                return []

            print(f"[Stage A] Found {len(candidates)} candidates")

            # STAGE B: HTTP Pre-filter (eliminate out-of-stock)
            print(f"[Stage B] Pre-filtering {len(candidates)} candidates...")
            candidate_urls = [c.pdp_url for c in candidates if c.pdp_url]

            if not candidate_urls:
                print("[Stage B] No valid URLs to pre-filter")
                return []

            prefiltered: List[ProductDetails] = await self.http_prefilter.filter_batch(
                urls=candidate_urls,
                required_brand=filters.get("brand") if filters else None,
                max_price=max_price
            )

            print(f"[Stage B] {len(prefiltered)}/{len(candidates)} passed pre-filter")

            if not prefiltered:
                print("[Stage B] No products passed pre-filter")
                return []

            # STAGE C: Retailer API Connectors (skip browser when possible)
            print(f"[Stage C] Checking retailer APIs...")
            prefiltered_urls = [p.canonical_url or p.url for p in prefiltered]
            api_verified: List[VariantDetails] = await self.api_connectors.check_batch(
                urls=prefiltered_urls,
                required_size=filters.get("size") if filters else None,
                required_color=filters.get("color") if filters else None
            )

            print(f"[Stage C] {len(api_verified)} products verified via API")

            # Convert API-verified products to Product objects
            api_products = []
            for variant in api_verified:
                if variant.available_for_sale:
                    api_products.append(Product(
                        id=variant.variant_id,
                        title=variant.title,
                        price=variant.price or 0.0,
                        currency=variant.currency,
                        url=variant.url,
                        image=variant.image_url,
                        retailer=variant.retailer_domain,
                        source="custom_pipeline_api",
                        relevance_score=0.95,  # High score for API-verified
                        in_stock=variant.in_stock,
                        brand=variant.brand,
                        color=variant.color,
                        size=variant.size
                    ))

            # Determine which products still need browser verification
            api_verified_urls = set(v.url for v in api_verified)
            remaining_for_browser = [
                p for p in prefiltered
                if (p.canonical_url or p.url) not in api_verified_urls
            ]

            print(f"[Stage C→D] {len(remaining_for_browser)} products need browser verification")

            # STAGE D: Playwright Verification (only for non-API products)
            browser_verified_products = []
            if remaining_for_browser:
                print(f"[Stage D] Browser-verifying {len(remaining_for_browser)} products...")

                # Limit to top 10 for Playwright (expensive operation)
                remaining_urls = [p.canonical_url or p.url for p in remaining_for_browser[:10]]

                # NOTE: Playwright verification is currently a placeholder
                # Real implementation requires integration with Playwright MCP tools
                playwright_verified: List[VerifiedProduct] = await self.playwright_verifier.verify_batch(
                    urls=remaining_urls,
                    required_size=filters.get("size") if filters else None,
                    required_color=filters.get("color") if filters else None,
                    zip_code=filters.get("zip_code", "10001") if filters else "10001"
                )

                print(f"[Stage D] {len(playwright_verified)} products browser-verified")

                # Convert Playwright-verified products to Product objects
                for verified in playwright_verified:
                    if verified.playwright_verified and verified.in_stock:
                        browser_verified_products.append(Product(
                            id=verified.canonical_url,
                            title=verified.title,
                            price=verified.price or 0.0,
                            currency=verified.currency,
                            url=verified.canonical_url,
                            image=verified.image_url,
                            retailer=verified.retailer_domain,
                            source="custom_pipeline_browser",
                            relevance_score=0.90,  # High score for browser-verified
                            in_stock=verified.in_stock,
                            brand=verified.brand,
                            color=verified.color,
                            size=verified.size
                        ))

            # Combine API + Browser verified products
            all_verified = api_products + browser_verified_products

            if not all_verified:
                print("[Stage D] No products passed verification")
                return []

            # STAGE E: Link Hardening (final validation)
            print(f"[Stage E] Hardening {len(all_verified)} links...")
            products_dict = [
                {
                    'url': p.url,
                    'canonical_url': p.url,
                    'title': p.title,
                    'brand': p.brand,
                    'price': p.price,
                    'currency': p.currency,
                    'size': p.size,
                    'color': p.color,
                    'image_url': p.image
                }
                for p in all_verified
            ]

            hardened: List[HardenedLink] = await self.link_hardener.harden_batch(products_dict)

            print(f"[Stage E] {len(hardened)}/{len(all_verified)} links hardened")

            # Convert hardened links to Product objects
            final_products = []
            for link in hardened:
                if link.is_valid:
                    final_products.append(Product(
                        id=link.canonical_url,
                        title=link.title,
                        price=link.price or 0.0,
                        currency=link.currency,
                        url=link.final_url or link.canonical_url,
                        image=link.image_url,
                        retailer=link.retailer_domain,
                        source="custom_pipeline",
                        relevance_score=0.95,  # Very high score for fully verified products
                        in_stock=True,  # All verified products are in stock
                        brand=link.brand,
                        color=link.color,
                        size=link.size
                    ))

            print(f"[Custom Pipeline] Final: {len(final_products)} products with 95%+ working links")
            return final_products

        except Exception as e:
            print(f"Custom pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            raise  # Re-raise to trigger fail-fast logic

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

    async def _search_oxylabs(
        self,
        descriptor: str,
        max_price: float,
        location: Optional[str]
    ) -> List[Product]:
        """
        Search using Oxylabs Google Shopping (PRIMARY SOURCE - replaces SearchAPI).

        Provides best coverage, filtering, and real-time data via Oxylabs scraping API.
        """
        try:
            print(f"[Oxylabs] Searching Google Shopping for: {descriptor[:50]}...")
            products = await self.oxylabs_client.search_products(
                descriptor=descriptor,
                price_max=max_price,
                location=location,
                max_results=20,  # Get top 20 from Oxylabs
                prefer_new=True,
                prefer_free_delivery=False  # Don't restrict too much
            )
            print(f"[Oxylabs] Found {len(products)} products")
            return products

        except Exception as e:
            print(f"Oxylabs search failed: {e}")
            raise  # Re-raise to trigger fail-fast logic

    async def _search_searchapi(
        self,
        descriptor: str,
        max_price: float,
        location: Optional[str]
    ) -> List[Product]:
        """
        Search using SearchAPI.io Google Shopping (DEPRECATED - replaced by Oxylabs).

        Provides best coverage, filtering, and real-time data.
        """
        try:
            print(f"[SearchAPI] Searching Google Shopping for: {descriptor[:50]}...")
            products = await self.searchapi_client.search_products(
                descriptor=descriptor,
                price_max=max_price,
                location=location,
                max_results=20,  # Get top 20 from SearchAPI
                prefer_new=True,
                prefer_free_delivery=False  # Don't restrict too much
            )
            print(f"[SearchAPI] Found {len(products)} products")
            return products

        except Exception as e:
            print(f"SearchAPI search failed: {e}")
            raise  # Re-raise to trigger fail-fast logic

    async def _search_retailed(
        self,
        descriptor: str,
        max_price: float,
        preferred_retailers: Optional[List[str]]
    ) -> List[Product]:
        """
        Search using Retailed.io (COMPLEMENTARY SOURCE).

        Best for retailer-specific searches (Nike, Zara, StockX, etc.).
        """
        try:
            print(f"[Retailed.io] Searching retailers for: {descriptor[:50]}...")
            products = await self.retailed_client.search_products(
                descriptor=descriptor,
                preferred_retailers=preferred_retailers,
                price_max=max_price,
                max_results=10  # Fewer results due to credit limits
            )
            print(f"[Retailed.io] Found {len(products)} products")
            return products

        except Exception as e:
            print(f"Retailed.io search failed: {e}")
            raise  # Re-raise to trigger fail-fast logic

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

    async def _search_openserp(
        self,
        descriptor: str,
        max_price: float
    ) -> List[Product]:
        """
        Search using OpenSERP local scraper (PRIMARY source).

        OpenSERP provides free access to Google, Bing, DuckDuckGo search results
        by running a local scraper on port 7001.

        Args:
            descriptor: Search query (e.g., "black leather heels women")
            max_price: Maximum price filter (unused - OpenSERP doesn't support price filtering)

        Returns:
            List of Product objects
        """
        try:
            print(f"[OpenSERP] Searching for: {descriptor}")

            # Search via OpenSERP megasearch (Google + Bing + DuckDuckGo)
            candidates = await self.openserp_client.search_products(
                query=descriptor,
                max_results=20,
                engines=["google", "bing", "duckduckgo"]
            )

            if not candidates:
                print("[OpenSERP] No products found")
                return []

            # Convert OpenSERP candidates to Product objects
            products = []
            for candidate in candidates:
                # Calculate relevance score based on search rank
                # Rank 1 = 1.0, Rank 2 = 0.95, Rank 3 = 0.90, etc.
                relevance_score = max(0.5, 1.0 - (candidate.rank * 0.05))

                # Generate unique ID from URL
                product_id = f"openserp_{abs(hash(candidate.url)) % 10**10}"

                product = Product(
                    id=product_id,
                    title=candidate.title,
                    url=candidate.url,
                    price=None,  # OpenSERP doesn't extract prices from snippets
                    image=None,  # OpenSERP doesn't provide images
                    retailer=candidate.engine.capitalize(),  # Use search engine as retailer
                    description=candidate.description[:200] if candidate.description else "",
                    relevance_score=relevance_score,
                    source="openserp"  # Track as OpenSERP source
                )
                products.append(product)

            print(f"[OpenSERP] Found {len(products)} products from {len(set(c.engine for c in candidates))} engines")

            # Resolve browse/search page links to actual product links (if enabled)
            if config.ENABLE_LINK_VERIFICATION and len(products) > 0:
                print(f"[OpenSERP] Resolving {len(products)} browse/search pages to product links...")
                try:
                    from services.link_resolver import resolve_openserp_products

                    # Create query hints for better resolution
                    query_hints = {p.id: descriptor for p in products}

                    # Resolve links
                    resolved_products = await resolve_openserp_products(products, query_hints)

                    if resolved_products:
                        print(f"[OpenSERP] Link resolution: {len(products)} → {len(resolved_products)} products")
                        return resolved_products
                    else:
                        print("[OpenSERP] Link resolution failed, using original links")
                except Exception as e:
                    print(f"[OpenSERP] Link resolution error: {e}, using original links")
                    import traceback
                    traceback.print_exc()

            return products

        except Exception as e:
            print(f"[OpenSERP] Search failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def _search_claude_web(
        self,
        descriptor: str,
        max_price: float,
        preferred_retailers: Optional[List[str]] = None
    ) -> List[Product]:
        """
        Search using Claude web search (FALLBACK for better product URLs).

        Claude can use web search to find actual product pages with verified URLs,
        prices, and retailer information. More accurate than traditional scraping.
        """
        try:
            print(f"[ClaudeWeb] Searching for: {descriptor}")

            # Search via Claude web search
            candidates = await self.claude_web_search_client.search_products(
                query=descriptor,
                max_results=20,
                max_price=max_price,
                preferred_retailers=preferred_retailers
            )

            if not candidates:
                print("[ClaudeWeb] No products found")
                return []

            # Convert to Product objects
            products = []
            for candidate in candidates:
                # Generate unique ID from URL
                product_id = f"claude_web_{abs(hash(candidate.url)) % 10**10}"

                # Calculate relevance score (Claude web search is highly accurate)
                relevance_score = 0.95

                product = Product(
                    id=product_id,
                    title=candidate.title,
                    url=candidate.url,
                    price=candidate.price,
                    currency=candidate.currency or "USD",
                    image=candidate.image_url,
                    retailer=candidate.retailer or "Unknown",
                    description=candidate.description[:200] if candidate.description else "",
                    relevance_score=relevance_score,
                    source="claude_web_search"  # Track as Claude web search source
                )
                products.append(product)

            print(f"[ClaudeWeb] Found {len(products)} products with verified URLs and prices")
            return products

        except Exception as e:
            print(f"[ClaudeWeb] Search failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def _search_visual(
        self,
        descriptor: str,
        max_price: float
    ) -> List[Product]:
        """
        Search using visual scraping (FALLBACK - Playwright + Claude Vision).

        This method takes screenshots of Google Shopping and uses Claude Vision API
        to extract product information. More robust than CSS selectors but slower.

        Args:
            descriptor: Search query (e.g., "black leather heels women")
            max_price: Maximum price filter

        Returns:
            List of Product objects
        """
        try:
            if not self.visual_scraper:
                print("[Visual] Visual scraper not initialized")
                return []

            print(f"[Visual] Starting visual scraping for: {descriptor}")

            # Visual scraping via Playwright + Claude Vision
            candidates = await self.visual_scraper.scrape_google_shopping(
                query=descriptor,
                max_results=10,  # Fewer results since it's slower
                max_price=max_price
            )

            if not candidates:
                print("[Visual] No products found")
                return []

            # Convert visual scraping candidates to Product objects
            products = []
            for candidate in candidates:
                # Parse price from string format (e.g., "$89.99" -> 89.99)
                price_val = None
                if candidate.price:
                    try:
                        # Remove currency symbols and commas
                        price_str = candidate.price.replace('$', '').replace('₹', '').replace(',', '')
                        price_val = float(price_str)
                    except (ValueError, AttributeError):
                        pass

                # Build description with retailer info
                description = candidate.title
                if candidate.retailer:
                    description = f"{candidate.retailer} - {candidate.title}"

                # Generate unique ID from URL
                product_id = f"visual_{abs(hash(candidate.url)) % 10**10}"

                product = Product(
                    id=product_id,
                    title=candidate.title,
                    url=candidate.url,
                    price=price_val,
                    image=candidate.image_url,
                    retailer=candidate.retailer or "Unknown",
                    description=description[:200] if description else "",
                    relevance_score=0.8,  # Slightly lower since it's fallback
                    source="visual_scraping"
                )
                products.append(product)

            print(f"[Visual] Found {len(products)} products via visual scraping")
            return products

        except Exception as e:
            print(f"[Visual] Search failed: {e}")
            import traceback
            traceback.print_exc()
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
            # Price filter - skip products without price info or above max_price
            if product.price is not None and product.price > max_price:
                continue

            # Retailer filter - APPLY TO ALL PRODUCTS
            if retailers_allowlist and product.retailer:
                # Case-insensitive matching for retailer names
                retailer_lower = product.retailer.lower()
                allowlist_lower = [r.lower() for r in retailers_allowlist]

                if retailer_lower not in allowlist_lower:
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
                "openserp": 1.0,  # PRIMARY: OpenSERP local scraper (Google+Bing+DuckDuckGo)
                "claude_web_search": 0.98,  # Claude web search with verified URLs and prices
                "searchapi_shopping": 0.95,  # SearchAPI Google Shopping (quota exhausted)
                "web_search": 0.90,  # Real products from actual web search
                "asos": 0.85,  # Fashion-specific, real API
                "google_shopping": 0.80,  # LEGACY: Real-time, broad coverage
                "retailed_io": 0.92,  # Retailer-specific scraping (when implemented)
                "vector_db": 0.70,  # Lower priority (currently disabled)
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
        # Handle products without price info (like OpenSERP results)
        if price is None:
            return 0.3  # Low score but not zero, since they could be relevant

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
_manager_started = False


async def ensure_manager_started():
    """Ensure OpenSERP manager is started (if enabled)."""
    global _manager_started
    if not _manager_started:
        service = get_product_search_service()
        if service.openserp_manager:
            await service.start()
        _manager_started = True


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
    # Ensure OpenSERP manager is started (if enabled)
    await ensure_manager_started()

    service = get_product_search_service()
    return await service.search_multi_source(descriptor, budget, filters, retailers_allowlist, k)
