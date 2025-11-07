"""
URL Resolver for Elara Fashion Recommendation System

This module resolves redirect URLs (especially Google Shopping redirects)
to actual product page URLs using Playwright.

Features:
- Detects Google Shopping redirect URLs
- Uses Playwright to follow redirects and extract final destination
- Parallel processing for batch resolution
- Caching to avoid redundant resolutions

Author: Elara Team
"""

import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse
import re

from contracts.models import Product

logger = logging.getLogger(__name__)


class URLResolver:
    """
    Resolves redirect URLs to actual product pages using Playwright.

    Handles Google Shopping redirect URLs and other intermediate redirects.
    """

    def __init__(
        self,
        concurrency: int = 5,
        timeout: int = 10000,
        max_retries: int = 2
    ):
        """
        Initialize URL resolver.

        Args:
            concurrency: Number of parallel browser instances
            timeout: Timeout per URL in milliseconds
            max_retries: Number of retry attempts per URL
        """
        self.concurrency = concurrency
        self.timeout = timeout
        self.max_retries = max_retries
        self._semaphore = asyncio.Semaphore(concurrency)
        self._resolution_cache: Dict[str, str] = {}  # Cache resolved URLs

    @staticmethod
    def is_google_shopping_url(url: str) -> bool:
        """
        Check if URL is a Google Shopping redirect.

        Args:
            url: URL to check

        Returns:
            True if it's a Google Shopping URL
        """
        if not url:
            return False

        return (
            "google.com/search" in url or
            "shopping.google.com" in url or
            "#oshopproduct" in url or
            "udm=28" in url  # Google Shopping parameter
        )

    @staticmethod
    def needs_resolution(url: str) -> bool:
        """
        Check if URL needs resolution (is a redirect URL).

        Args:
            url: URL to check

        Returns:
            True if URL needs resolution
        """
        if not url:
            return False

        # Check for Google Shopping redirects
        if URLResolver.is_google_shopping_url(url):
            return True

        # Check for other redirect patterns
        redirect_patterns = [
            r'redirect',
            r'redir',
            r'click\.linksynergy',
            r'anrdoezrs\.net',
            r'prf\.hn',  # Skimlinks
            r'go\.redirectingat',  # Skimlinks
        ]

        for pattern in redirect_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True

        return False

    async def resolve_url(
        self,
        url: str
    ) -> Optional[str]:
        """
        Resolve a redirect URL to its final destination using HTTP redirects.

        For Google Shopping URLs, we extract embedded product information
        from the URL parameters instead of using Playwright (for speed).

        Args:
            url: The redirect URL to resolve

        Returns:
            Final destination URL, or None if resolution failed
        """
        # Check cache first
        if url in self._resolution_cache:
            logger.debug(f"URL resolution cache hit: {url[:60]}...")
            return self._resolution_cache[url]

        # If it doesn't need resolution, return as-is
        if not self.needs_resolution(url):
            return url

        # For Google Shopping URLs, try to extract merchant link from HTML
        if self.is_google_shopping_url(url):
            try:
                # Google Shopping URLs sometimes have the product URL embedded
                # Let's try to parse it from the URL parameters or fetch the page
                import httpx
                async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
                    try:
                        response = await client.get(url, follow_redirects=True)
                        final_url = str(response.url)

                        # If we got redirected off Google, use that
                        if not self.is_google_shopping_url(final_url):
                            logger.info(f"✓ HTTP resolved: {url[:40]}... → {final_url[:60]}...")
                            self._resolution_cache[url] = final_url
                            return final_url

                        # Try to extract from HTML
                        html = response.text
                        # Look for merchant links in the HTML
                        merchant_patterns = [
                            r'href="(https?://www\.nordstrom\.com/[^"]+)"',
                            r'href="(https?://www1\.macys\.com/[^"]+)"',
                            r'href="(https?://www\.asos\.com/[^"]+)"',
                            r'href="(https?://www\.nike\.com/[^"]+)"',
                            r'href="(https?://[^"]+/product[^"]*)"',
                        ]

                        import re
                        for pattern in merchant_patterns:
                            matches = re.findall(pattern, html, re.IGNORECASE)
                            if matches:
                                # Use the first match
                                product_url = matches[0]
                                logger.info(f"✓ Extracted from HTML: {url[:40]}... → {product_url[:60]}...")
                                self._resolution_cache[url] = product_url
                                return product_url

                    except Exception as e:
                        logger.debug(f"HTTP resolution failed: {str(e)}")

            except Exception as e:
                logger.warning(f"Failed to resolve Google Shopping URL: {str(e)}")

            # If we couldn't resolve, return original
            logger.warning(f"Could not resolve Google Shopping URL: {url[:60]}...")
            return url

        # For other redirect URLs, try simple HTTP follow
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
                response = await client.get(url)
                final_url = str(response.url)
                if final_url != url:
                    logger.info(f"✓ Resolved: {url[:40]}... → {final_url[:60]}...")
                    self._resolution_cache[url] = final_url
                    return final_url
        except Exception as e:
            logger.warning(f"URL resolution failed: {str(e)}")

        return url  # Fall back to original URL

    async def resolve_batch(
        self,
        products: List[Product]
    ) -> List[Product]:
        """
        Resolve URLs for a batch of products in parallel.

        Args:
            products: List of Product objects with potentially redirect URLs

        Returns:
            List of Product objects with resolved URLs
        """
        if not products:
            return []

        # Check which products need resolution
        products_needing_resolution = [
            p for p in products if self.needs_resolution(p.url)
        ]

        if not products_needing_resolution:
            logger.info("No products need URL resolution")
            return products

        logger.info(
            f"[URL Resolution] Resolving {len(products_needing_resolution)}/{len(products)} "
            f"redirect URLs..."
        )

        # Resolve URLs in parallel (with semaphore limiting concurrency)
        resolution_tasks = [
            self.resolve_url(product.url)
            for product in products_needing_resolution
        ]

        resolved_urls = await asyncio.gather(*resolution_tasks, return_exceptions=True)

        # Update products with resolved URLs
        url_mapping = {}
        for product, resolved_url in zip(products_needing_resolution, resolved_urls):
            if isinstance(resolved_url, Exception):
                logger.error(f"Exception resolving {product.url[:60]}: {str(resolved_url)}")
                url_mapping[product.url] = product.url  # Keep original
            elif resolved_url:
                url_mapping[product.url] = resolved_url
            else:
                url_mapping[product.url] = product.url  # Keep original

        # Create updated product list
        updated_products = []
        for product in products:
            if product.url in url_mapping and url_mapping[product.url] != product.url:
                # Create updated product with resolved URL
                updated_product = Product(
                    **{
                        **product.__dict__,
                        "url": url_mapping[product.url]
                    }
                )
                updated_products.append(updated_product)
            else:
                updated_products.append(product)

        resolved_count = sum(
            1 for old_url, new_url in url_mapping.items()
            if old_url != new_url and not URLResolver.is_google_shopping_url(new_url)
        )

        logger.info(f"[URL Resolution] Successfully resolved {resolved_count}/{len(products_needing_resolution)} URLs")

        return updated_products

    def clear_cache(self):
        """Clear the URL resolution cache"""
        self._resolution_cache.clear()
        logger.info("URL resolution cache cleared")

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "cached_urls": len(self._resolution_cache),
            "cache_size_bytes": sum(len(k) + len(v) for k, v in self._resolution_cache.items())
        }


def get_resolution_stats(products: List[Product]) -> Dict:
    """
    Get statistics about URL resolution needs.

    Args:
        products: List of products

    Returns:
        Dictionary with resolution statistics
    """
    total = len(products)
    google_shopping = sum(1 for p in products if URLResolver.is_google_shopping_url(p.url))
    needs_resolution = sum(1 for p in products if URLResolver.needs_resolution(p.url))

    return {
        "total_products": total,
        "google_shopping_urls": google_shopping,
        "needs_resolution": needs_resolution,
        "percentage_needing_resolution": (needs_resolution / total * 100) if total > 0 else 0
    }
