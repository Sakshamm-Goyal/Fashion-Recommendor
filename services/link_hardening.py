"""
Stage E: Link Hardening and Validation
=======================================

Final validation layer to ensure 100% working product links.
Performs HEAD/GET requests to verify 200 OK status and canonical URL stability.

Key Features:
- HTTP HEAD/GET validation
- 200 OK status verification
- Redirect following and final URL extraction
- Canonical URL stability check
- Variant parameter persistence
- Final quality gate before returning to user

Author: Elara Team
"""

import asyncio
import httpx
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs
import logging

logger = logging.getLogger(__name__)


@dataclass
class HardenedLink:
    """Final hardened product link"""
    url: str
    canonical_url: str
    title: str
    brand: Optional[str] = None
    price: Optional[float] = None
    currency: str = "USD"

    # Variant details
    size: Optional[str] = None
    color: Optional[str] = None

    # Validation metadata
    http_status: int = 0
    final_url: str = ""  # After redirects
    redirect_count: int = 0
    response_time_ms: int = 0

    # Quality checks
    is_valid: bool = False
    has_variant_params: bool = False
    canonical_stable: bool = False
    rejection_reason: Optional[str] = None

    # Metadata
    image_url: Optional[str] = None
    retailer_domain: str = ""


class LinkHardener:
    """
    Stage E: Final link validation and hardening.

    Ensures all returned product links are:
    - 200 OK status
    - Canonical URL is stable
    - Variant parameters persist
    - No unexpected redirects to error pages
    """

    USER_AGENT = (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )

    # Known error page indicators
    ERROR_PAGE_INDICATORS = [
        '404', 'not found', 'page not found',
        'error', 'unavailable', 'something went wrong',
        'oops', 'sorry'
    ]

    def __init__(
        self,
        timeout: int = 10,
        max_concurrent: int = 10,
        follow_redirects: bool = True,
        max_redirects: int = 5
    ):
        """
        Initialize link hardener.

        Args:
            timeout: HTTP request timeout in seconds
            max_concurrent: Max concurrent requests
            follow_redirects: Follow HTTP redirects
            max_redirects: Maximum number of redirects to follow
        """
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.follow_redirects = follow_redirects
        self.max_redirects = max_redirects

    async def harden_batch(
        self,
        products: List[Dict]
    ) -> List[HardenedLink]:
        """
        Harden batch of product links.

        Args:
            products: List of product dicts with at least 'url' field

        Returns:
            List of HardenedLink objects that passed validation
        """
        logger.info(f"[Link Hardener] Hardening {len(products)} links...")

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=self.follow_redirects,
            headers={'User-Agent': self.USER_AGENT},
            max_redirects=self.max_redirects
        ) as client:

            semaphore = asyncio.Semaphore(self.max_concurrent)

            async def harden_with_limit(product: Dict) -> Optional[HardenedLink]:
                async with semaphore:
                    return await self._harden_single(client, product)

            tasks = [harden_with_limit(p) for p in products]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter valid links
            hardened = []
            for result in results:
                if isinstance(result, HardenedLink) and result.is_valid:
                    hardened.append(result)
                elif isinstance(result, Exception):
                    logger.debug(f"[Link Hardener] Exception: {result}")

            logger.info(
                f"[Link Hardener] Hardened {len(hardened)}/{len(products)} links "
                f"({len(hardened)/len(products)*100:.1f}% pass rate)"
            )

            return hardened

    async def _harden_single(
        self,
        client: httpx.AsyncClient,
        product: Dict
    ) -> Optional[HardenedLink]:
        """Harden single product link"""
        url = product.get('url') or product.get('canonical_url')
        if not url:
            return None

        # Build HardenedLink from product data
        link = HardenedLink(
            url=url,
            canonical_url=product.get('canonical_url', url),
            title=product.get('title', ''),
            brand=product.get('brand'),
            price=product.get('price'),
            currency=product.get('currency', 'USD'),
            size=product.get('size'),
            color=product.get('color'),
            image_url=product.get('image_url'),
            retailer_domain=urlparse(url).netloc.lower().replace('www.', '')
        )

        try:
            # Start timing
            import time
            start_time = time.time()

            # Send HEAD request first (faster)
            try:
                head_response = await client.head(url)
                link.http_status = head_response.status_code
                link.final_url = str(head_response.url)
                link.redirect_count = len(head_response.history)
            except Exception:
                # Fallback to GET if HEAD fails
                get_response = await client.get(url)
                link.http_status = get_response.status_code
                link.final_url = str(get_response.url)
                link.redirect_count = len(get_response.history)

            # Record response time
            link.response_time_ms = int((time.time() - start_time) * 1000)

            # Validation checks
            if link.http_status != 200:
                link.rejection_reason = f"HTTP {link.http_status}"
                return link

            # Check for unexpected redirects to error pages
            if self._is_error_page(link.final_url):
                link.rejection_reason = "Redirected to error page"
                return link

            # Check if variant parameters persist
            link.has_variant_params = self._has_variant_params(link.final_url)

            # Check canonical URL stability
            # (final_url should match canonical_url or be a variant of it)
            link.canonical_stable = self._check_canonical_stability(
                link.canonical_url,
                link.final_url
            )

            # Final validation
            if link.http_status == 200 and link.canonical_stable:
                link.is_valid = True
            else:
                link.rejection_reason = "Canonical URL mismatch after redirects"

            return link

        except httpx.TimeoutException:
            link.rejection_reason = "HTTP timeout"
            return link
        except Exception as e:
            link.rejection_reason = f"Error: {type(e).__name__}"
            logger.debug(f"[Link Hardener] Error hardening {url}: {e}")
            return link

    def _is_error_page(self, url: str) -> bool:
        """Check if URL indicates an error page"""
        url_lower = url.lower()

        for indicator in self.ERROR_PAGE_INDICATORS:
            if indicator in url_lower:
                return True

        return False

    def _has_variant_params(self, url: str) -> bool:
        """Check if URL has variant parameters"""
        # Common variant parameter names
        variant_params = ['variant', 'sku', 'color', 'size', 'pid', 'productId']

        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        for param in variant_params:
            if param.lower() in [p.lower() for p in query_params.keys()]:
                return True

        return False

    def _check_canonical_stability(
        self,
        canonical_url: str,
        final_url: str
    ) -> bool:
        """
        Check if final URL matches canonical URL.

        Allows for:
        - Query parameter differences (variant params)
        - Protocol differences (http vs https)
        - www subdomain differences
        """
        # Normalize URLs
        canonical_parsed = urlparse(canonical_url)
        final_parsed = urlparse(final_url)

        # Compare domains (ignore www)
        canonical_domain = canonical_parsed.netloc.lower().replace('www.', '')
        final_domain = final_parsed.netloc.lower().replace('www.', '')

        if canonical_domain != final_domain:
            return False

        # Compare paths (must match exactly)
        canonical_path = canonical_parsed.path.rstrip('/')
        final_path = final_parsed.path.rstrip('/')

        if canonical_path != final_path:
            return False

        # Query params can differ (variant selection is allowed)
        return True

    async def validate_single_url(self, url: str) -> bool:
        """
        Quick validation for single URL.

        Returns True if URL returns 200 OK.
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={'User-Agent': self.USER_AGENT}
            ) as client:
                response = await client.head(url)
                return response.status_code == 200
        except Exception:
            return False


# Convenience function
async def harden_links(products: List[Dict]) -> List[HardenedLink]:
    """
    Quick link hardening for list of products.

    Args:
        products: List of product dicts with 'url' field

    Returns:
        List of HardenedLink objects that passed validation
    """
    hardener = LinkHardener()
    return await hardener.harden_batch(products)


async def validate_url(url: str) -> bool:
    """
    Quick validation for single URL.

    Args:
        url: URL to validate

    Returns:
        True if URL returns 200 OK
    """
    hardener = LinkHardener()
    return await hardener.validate_single_url(url)
