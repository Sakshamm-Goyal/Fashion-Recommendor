"""
Link Resolver Service for OpenSERP Results

This service resolves OpenSERP search/browse page links into actual product links
using Playwright MCP for browser automation.

OpenSERP returns general search result links like:
- https://www.nordstrom.com/browse/women/clothing/coats-jackets?filterByColor=black
- https://www.myntra.com/women-black-leather-jackets

This resolver:
1. Opens these pages in Playwright
2. Finds actual product links on the page
3. Returns working direct product URLs

Author: Elara Team
"""

import asyncio
import logging
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse, urljoin

from contracts.models import Product

logger = logging.getLogger(__name__)


@dataclass
class ResolvedProduct:
    """A resolved product link with metadata"""
    original_url: str
    resolved_url: str
    title: str
    price: Optional[float] = None
    currency: str = "USD"
    image: Optional[str] = None
    retailer: Optional[str] = None


class LinkResolver:
    """
    Resolves search/browse page links into direct product links using Playwright.

    Strategy:
    1. Navigate to browse/search page
    2. Extract product links from the page
    3. Return list of actual product URLs
    4. Validate links lead to real products
    """

    # Common product link patterns for various retailers
    PRODUCT_LINK_PATTERNS = {
        "nordstrom": r"/s/[^/]+/\d+",
        "macys": r"/shop/product/",
        "amazon": r"/dp/[A-Z0-9]+",
        "revolve": r"/[^/]+/dp/",
        "urbanoutfitters": r"/shop/[^/]+",
        "asos": r"/prd/\d+",
        "zara": r"/(.*?)/p/\d+",
        "hm": r"/productpage\.",
        "myntra": r"/\d+/buy",
    }

    # Product card selectors for extracting links
    PRODUCT_SELECTORS = [
        "article a[href*='/product']",
        "article a[href*='/p/']",
        "article a[href*='/dp/']",
        "article a[href*='/shop/']",
        ".product-card a",
        ".product-tile a",
        ".product-item a",
        "a.product-link",
        "[data-product-id] a",
        "a[href*='/s/']",  # Nordstrom specific
    ]

    def __init__(
        self,
        max_products_per_page: int = 5,
        timeout: int = 10000,
        concurrency: int = 3
    ):
        """
        Initialize link resolver.

        Args:
            max_products_per_page: Max products to extract from each browse page
            timeout: Timeout per page in milliseconds
            concurrency: Number of parallel browser instances
        """
        self.max_products_per_page = max_products_per_page
        self.timeout = timeout
        self.concurrency = concurrency
        self._semaphore = asyncio.Semaphore(concurrency)

    def _detect_retailer_from_url(self, url: str) -> Optional[str]:
        """Detect retailer name from URL"""
        try:
            domain = urlparse(url).netloc.lower()

            # Map domains to retailer names
            retailer_map = {
                "nordstrom.com": "Nordstrom",
                "macys.com": "Macy's",
                "amazon.com": "Amazon",
                "revolve.com": "Revolve",
                "urbanoutfitters.com": "Urban Outfitters",
                "asos.com": "ASOS",
                "zara.com": "Zara",
                "hm.com": "H&M",
                "myntra.com": "Myntra",
            }

            for domain_pattern, retailer_name in retailer_map.items():
                if domain_pattern in domain:
                    return retailer_name

            return None
        except:
            return None

    def _is_product_link(self, url: str, base_domain: str) -> bool:
        """Check if URL looks like a product page"""
        if not url or url.startswith(("javascript:", "mailto:", "#")):
            return False

        # Check against known product URL patterns
        for retailer, pattern in self.PRODUCT_LINK_PATTERNS.items():
            if retailer in base_domain.lower():
                if re.search(pattern, url):
                    return True

        # Generic product patterns
        generic_patterns = [
            r"/product/",
            r"/p/\d+",
            r"/dp/",
            r"/shop/[^/]+$",
            r"/\d{6,}",  # Product IDs
        ]

        for pattern in generic_patterns:
            if re.search(pattern, url):
                return True

        return False

    async def resolve_link(
        self,
        browse_url: str,
        query_hint: Optional[str] = None
    ) -> List[ResolvedProduct]:
        """
        Resolve a single browse/search page into product links.

        Args:
            browse_url: The search/browse page URL
            query_hint: Original search query for context

        Returns:
            List of resolved product links
        """
        async with self._semaphore:
            try:
                logger.info(f"[LinkResolver] Resolving: {browse_url}")

                # Import Playwright MCP client here to avoid circular imports
                try:
                    from integrations.playwright_mcp_client import PlaywrightMCPClient
                except ImportError:
                    logger.error("[LinkResolver] Playwright MCP not available")
                    return []

                client = PlaywrightMCPClient()

                # Navigate to the browse page
                await client.navigate(browse_url, timeout=self.timeout)

                # Wait longer for JavaScript to fully render products
                logger.info("[LinkResolver] Waiting for page to fully load...")
                await asyncio.sleep(5)

                # Extract product links from HTML
                base_domain = urlparse(browse_url).netloc
                retailer = self._detect_retailer_from_url(browse_url)

                product_links = []

                # Use JavaScript evaluation to extract all links from the page
                # This is more reliable than parsing HTML
                js_script = """
                () => {
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    return links.map(a => a.href).filter(href => href && href.startsWith('http'));
                }
                """

                all_links = await client.evaluate(js_script)

                if not all_links:
                    logger.warning(f"[LinkResolver] No links found via JavaScript, trying HTML parsing")

                    # Fallback to HTML parsing
                    html = await client.get_visible_html(
                        clean_html=False,  # Don't clean, we need the links!
                        remove_scripts=False,  # Keep everything
                        max_length=200000
                    )

                    # Parse HTML for product links
                    href_pattern = r'href=["\']([^"\']+)["\']'
                    all_links = re.findall(href_pattern, html)

                    # Make absolute URLs
                    absolute_links = []
                    for link in all_links:
                        if link.startswith('/'):
                            absolute_links.append(urljoin(browse_url, link))
                        elif link.startswith('http'):
                            absolute_links.append(link)

                    all_links = absolute_links

                logger.info(f"[LinkResolver] Found {len(all_links)} total links on page")

                # Filter for product links
                for link in all_links:
                    if self._is_product_link(link, base_domain):
                        product_links.append(link)

                        if len(product_links) >= self.max_products_per_page:
                            break

                logger.info(f"[LinkResolver] Extracted {len(product_links)} product links")

                # Convert to ResolvedProduct objects
                resolved = []
                for url in product_links:
                    resolved.append(ResolvedProduct(
                        original_url=browse_url,
                        resolved_url=url,
                        title=f"Product from {retailer or base_domain}",
                        retailer=retailer
                    ))

                await client.close()
                return resolved

            except Exception as e:
                logger.error(f"[LinkResolver] Error resolving {browse_url}: {e}")
                return []

    async def resolve_products(
        self,
        products: List[Product],
        query_hints: Optional[Dict[str, str]] = None
    ) -> List[Product]:
        """
        Resolve browse/search page links in products to actual product links.

        Args:
            products: List of Product objects with browse/search URLs
            query_hints: Optional mapping of product IDs to search queries

        Returns:
            Expanded list of Product objects with resolved direct product links
        """
        logger.info(f"[LinkResolver] Resolving links for {len(products)} products")

        # Create resolution tasks
        tasks = []
        for product in products:
            query_hint = query_hints.get(product.id) if query_hints else None
            tasks.append(self.resolve_link(product.url, query_hint))

        # Resolve in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert resolved products back to Product objects
        resolved_products = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[LinkResolver] Failed to resolve product {i}: {result}")
                continue

            if not result:
                # No products found, keep original
                resolved_products.append(products[i])
                continue

            # Add all resolved products
            original = products[i]
            for resolved in result:
                resolved_products.append(Product(
                    id=f"{original.id}_resolved_{len(resolved_products)}",
                    title=resolved.title,
                    price=resolved.price or original.price,
                    currency=resolved.currency,
                    url=resolved.resolved_url,
                    image=resolved.image or original.image,
                    retailer=resolved.retailer or original.retailer,
                    brand=original.brand,
                    source="openserp_resolved"
                ))

        logger.info(f"[LinkResolver] Resolved {len(products)} browse pages → {len(resolved_products)} product links")
        return resolved_products


# Singleton instance
_resolver_instance = None


def get_link_resolver() -> LinkResolver:
    """Get or create link resolver singleton"""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = LinkResolver()
    return _resolver_instance


async def resolve_openserp_products(
    products: List[Product],
    query_hints: Optional[Dict[str, str]] = None
) -> List[Product]:
    """
    Convenience function to resolve OpenSERP products.

    Args:
        products: List of Product objects from OpenSERP
        query_hints: Optional search queries for context

    Returns:
        Expanded list with resolved product links
    """
    resolver = get_link_resolver()
    return await resolver.resolve_products(products, query_hints)
