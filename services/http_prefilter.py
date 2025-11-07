"""
Stage B: HTTP Pre-Filter (No Browser)
======================================

Lightweight HTTP-based filtering to eliminate bad candidates before Playwright.
Uses JSON-LD parsing and canonical URL extraction.

Key Features:
- HTTP GET + parse HTML (no browser)
- Extract JSON-LD Product/Offer schema
- Check availability status (InStock, OutOfStock, etc.)
- Extract canonical URL
- Identify variant URLs from embedded JSON
- 10-20x faster than browser-based verification

Author: Elara Team
"""

import asyncio
import httpx
import json
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProductDetails:
    """Extracted product details from HTTP pre-filter"""
    url: str
    canonical_url: Optional[str] = None
    title: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[float] = None
    currency: str = "USD"
    availability: Optional[str] = None  # InStock, OutOfStock, PreOrder, etc.
    in_stock: bool = False
    image_url: Optional[str] = None
    sku: Optional[str] = None

    # Variant detection
    has_variants: bool = False
    variant_data: Optional[Dict] = None  # Raw variant JSON
    variant_url: Optional[str] = None  # Direct variant URL if available

    # Metadata
    http_status: int = 0
    retailer_domain: str = ""
    json_ld_found: bool = False
    passed_prefilter: bool = False
    rejection_reason: Optional[str] = None


class HTTPPreFilter:
    """
    Stage B: HTTP-based pre-filtering without browser.

    Quickly eliminates out-of-stock and broken links before
    expensive Playwright verification.

    Success rate: ~50-60% elimination (10-20 candidates → 5-10 strong)
    """

    USER_AGENT = (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )

    AVAILABILITY_IN_STOCK = {
        'instock', 'in stock', 'https://schema.org/instock',
        'available', 'in_stock'
    }

    AVAILABILITY_OUT_OF_STOCK = {
        'outofstock', 'out of stock', 'https://schema.org/outofstock',
        'soldout', 'sold out', 'unavailable', 'out_of_stock'
    }

    def __init__(
        self,
        timeout: int = 5,
        max_concurrent: int = 10,
        follow_redirects: bool = True
    ):
        """
        Initialize HTTP pre-filter.

        Args:
            timeout: HTTP request timeout in seconds
            max_concurrent: Max concurrent HTTP requests
            follow_redirects: Follow HTTP redirects
        """
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.follow_redirects = follow_redirects

    async def filter_batch(
        self,
        urls: List[str],
        required_brand: Optional[str] = None,
        max_price: Optional[float] = None
    ) -> List[ProductDetails]:
        """
        Filter a batch of URLs through HTTP pre-filter.

        Args:
            urls: List of product URLs to check
            required_brand: If set, only keep products matching this brand
            max_price: If set, only keep products under this price

        Returns:
            List of ProductDetails that passed pre-filter
        """
        logger.info(f"[Pre-Filter] Checking {len(urls)} URLs...")

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=self.follow_redirects,
            headers={'User-Agent': self.USER_AGENT}
        ) as client:

            # Process in batches to control concurrency
            semaphore = asyncio.Semaphore(self.max_concurrent)

            async def check_with_limit(url: str) -> ProductDetails:
                async with semaphore:
                    return await self._check_single(client, url)

            tasks = [check_with_limit(url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter results
            passed = []
            for result in results:
                if isinstance(result, ProductDetails):
                    # Apply filters
                    if not result.passed_prefilter:
                        logger.debug(f"[Pre-Filter] Rejected: {result.rejection_reason}")
                        continue

                    # Brand filter
                    if required_brand and result.brand:
                        if required_brand.lower() not in result.brand.lower():
                            result.passed_prefilter = False
                            result.rejection_reason = f"Brand mismatch: {result.brand} != {required_brand}"
                            continue

                    # Price filter
                    if max_price and result.price:
                        if result.price > max_price:
                            result.passed_prefilter = False
                            result.rejection_reason = f"Price too high: ${result.price} > ${max_price}"
                            continue

                    passed.append(result)

                elif isinstance(result, Exception):
                    logger.debug(f"[Pre-Filter] Exception: {result}")

            logger.info(
                f"[Pre-Filter] Passed {len(passed)}/{len(urls)} URLs "
                f"({len(passed)/len(urls)*100:.1f}% pass rate)"
            )

            return passed

    async def _check_single(self, client: httpx.AsyncClient, url: str) -> ProductDetails:
        """Check single URL through HTTP pre-filter"""
        details = ProductDetails(url=url)
        details.retailer_domain = urlparse(url).netloc.lower().replace('www.', '')

        try:
            # HTTP GET
            response = await client.get(url)
            details.http_status = response.status_code
            details.url = str(response.url)  # Update to final URL after redirects

            if response.status_code != 200:
                details.rejection_reason = f"HTTP {response.status_code}"
                return details

            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract canonical URL
            details.canonical_url = self._extract_canonical(soup, url)

            # Extract JSON-LD
            json_ld_data = self._extract_json_ld(soup)
            if json_ld_data:
                details.json_ld_found = True
                self._parse_json_ld(json_ld_data, details)

            # Extract variant data from embedded JSON (retailer-specific)
            variant_json = self._extract_variant_json(soup)
            if variant_json:
                details.has_variants = True
                details.variant_data = variant_json

            # Final check: passed if in stock
            if details.in_stock:
                details.passed_prefilter = True
            else:
                details.rejection_reason = f"Not in stock: {details.availability}"

            return details

        except httpx.TimeoutException:
            details.rejection_reason = "HTTP timeout"
            return details
        except Exception as e:
            details.rejection_reason = f"Error: {type(e).__name__}"
            logger.debug(f"[Pre-Filter] Error checking {url}: {e}")
            return details

    def _extract_canonical(self, soup: BeautifulSoup, fallback_url: str) -> str:
        """Extract canonical URL from HTML"""
        canonical_tag = soup.find('link', rel='canonical')
        if canonical_tag and canonical_tag.get('href'):
            canonical = canonical_tag['href']
            # Make absolute if relative
            if not canonical.startswith('http'):
                canonical = urljoin(fallback_url, canonical)
            return canonical
        return fallback_url

    def _extract_json_ld(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract JSON-LD Product schema from HTML"""
        # Find all JSON-LD script tags
        json_ld_scripts = soup.find_all('script', type='application/ld+json')

        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)

                # Handle @graph arrays
                if isinstance(data, dict) and '@graph' in data:
                    data = data['@graph']

                # Handle arrays
                if isinstance(data, list):
                    for item in data:
                        if self._is_product_schema(item):
                            return item
                elif self._is_product_schema(data):
                    return data

            except (json.JSONDecodeError, AttributeError):
                continue

        return None

    def _is_product_schema(self, data: Dict) -> bool:
        """Check if JSON-LD data is a Product schema"""
        if not isinstance(data, dict):
            return False
        schema_type = data.get('@type', '').lower()
        return 'product' in schema_type

    def _parse_json_ld(self, json_ld: Dict, details: ProductDetails):
        """Parse JSON-LD Product schema into ProductDetails"""
        # Extract title
        if 'name' in json_ld:
            details.title = json_ld['name']

        # Extract brand
        if 'brand' in json_ld:
            brand_data = json_ld['brand']
            if isinstance(brand_data, dict):
                details.brand = brand_data.get('name')
            elif isinstance(brand_data, str):
                details.brand = brand_data

        # Extract SKU
        if 'sku' in json_ld:
            details.sku = json_ld['sku']

        # Extract image
        if 'image' in json_ld:
            image_data = json_ld['image']
            if isinstance(image_data, list) and image_data:
                details.image_url = image_data[0]
            elif isinstance(image_data, str):
                details.image_url = image_data

        # Extract offers (price + availability)
        if 'offers' in json_ld:
            self._parse_offers(json_ld['offers'], details)

    def _parse_offers(self, offers_data, details: ProductDetails):
        """Parse offers from JSON-LD"""
        # Offers can be a single dict or array
        offers_list = offers_data if isinstance(offers_data, list) else [offers_data]

        for offer in offers_list:
            if not isinstance(offer, dict):
                continue

            # Extract price
            if 'price' in offer:
                try:
                    details.price = float(offer['price'])
                except (ValueError, TypeError):
                    pass

            # Extract currency
            if 'priceCurrency' in offer:
                details.currency = offer['priceCurrency']

            # Extract availability
            if 'availability' in offer:
                availability = str(offer['availability']).lower()
                details.availability = availability

                # Check if in stock
                if any(stock_term in availability for stock_term in self.AVAILABILITY_IN_STOCK):
                    details.in_stock = True
                elif any(oos_term in availability for oos_term in self.AVAILABILITY_OUT_OF_STOCK):
                    details.in_stock = False

            # If found a valid offer, break (use first offer)
            if details.price is not None:
                break

    def _extract_variant_json(self, soup: BeautifulSoup) -> Optional[Dict]:
        """
        Extract embedded variant JSON (retailer-specific).

        Many retailers embed product variant data in:
        - <script> tags with JSON
        - data-* attributes
        - window.__INITIAL_STATE__ or similar

        This is retailer-specific, so we try common patterns.
        """
        # Pattern 1: Look for scripts with "variants" or "selectedVariant"
        scripts = soup.find_all('script', type='text/javascript')

        for script in scripts:
            if not script.string:
                continue

            # Look for common variant JSON patterns
            if 'variants' in script.string or 'selectedVariant' in script.string:
                # Try to extract JSON object
                json_match = re.search(r'({[\s\S]*?})', script.string)
                if json_match:
                    try:
                        variant_data = json.loads(json_match.group(1))
                        if 'variants' in variant_data:
                            return variant_data
                    except json.JSONDecodeError:
                        continue

        # Pattern 2: Look for data-product-json attributes (Shopify)
        product_json_elem = soup.find(attrs={'data-product-json': True})
        if product_json_elem:
            try:
                return json.loads(product_json_elem['data-product-json'])
            except (json.JSONDecodeError, KeyError):
                pass

        return None


# Convenience function
async def prefilter_urls(
    urls: List[str],
    required_brand: Optional[str] = None,
    max_price: Optional[float] = None,
    timeout: int = 5
) -> List[ProductDetails]:
    """
    Quick pre-filter for list of URLs.

    Args:
        urls: Product URLs to check
        required_brand: Optional brand filter
        max_price: Optional max price filter
        timeout: HTTP timeout in seconds

    Returns:
        List of ProductDetails that passed pre-filter
    """
    prefilter = HTTPPreFilter(timeout=timeout)
    return await prefilter.filter_batch(urls, required_brand, max_price)
