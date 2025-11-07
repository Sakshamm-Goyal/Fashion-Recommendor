"""
Oxylabs Web Scraper API Client for Google Shopping searches.

Uses Oxylabs' real-time scraping API to get Google Shopping results
for fashion products with proper US geo-location.

API Limits (Free Trial):
- Up to 2K results
- 10 requests/s
- $1 trial limit

Documentation: https://developers.oxylabs.io/scraping-solutions/web-scraper-api
"""

import logging
import requests
from typing import List, Dict, Optional
import json
from contracts.models import Product
import uuid

logger = logging.getLogger(__name__)


class OxylabsClient:
    """
    Client for Oxylabs Web Scraper API.

    Provides Google Shopping search with US geo-location and parsing.
    """

    def __init__(
        self,
        username: str = "elara_u1y0M",
        password: str = "AVFGxj4K3fx8n+i"
    ):
        """
        Initialize Oxylabs client.

        Args:
            username: Oxylabs API username
            password: Oxylabs API password
        """
        self.username = username
        self.password = password
        self.base_url = "https://realtime.oxylabs.io/v1/queries"

        logger.info(f"[Oxylabs] Initialized with username: {self.username}")

    def scrape_retailer_page(
        self,
        url: str,
        geo_location: str = "United States"
    ) -> Optional[str]:
        """
        Scrape a retailer category/product page using Oxylabs.

        This bypasses anti-bot protection to get the HTML content.
        Use this when Claude Web Search finds category pages and you need
        to extract actual product URLs from them.

        Args:
            url: Retailer page URL (category or product page)
            geo_location: Geographic location for scraping

        Returns:
            HTML content of the page, or None if failed
        """
        logger.info(f"[Oxylabs] Scraping retailer page: {url[:80]}...")

        try:
            # Use universal_ecommerce for e-commerce sites like Nordstrom, Zara, etc.
            payload = {
                "source": "universal_ecommerce",
                "url": url,
                "geo_location": geo_location
            }

            response = requests.post(
                self.base_url,
                auth=(self.username, self.password),
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=60
            )

            response.raise_for_status()
            data = response.json()

            logger.info(f"[Oxylabs] Response status: {response.status_code}")

            # Extract HTML content
            if 'results' in data and len(data['results']) > 0:
                html_content = data['results'][0].get('content', '')
                logger.info(f"[Oxylabs] Scraped {len(html_content)} bytes of HTML")
                return html_content
            else:
                logger.warning(f"[Oxylabs] No content in response")
                return None

        except requests.exceptions.HTTPError as e:
            logger.error(f"[Oxylabs] HTTP error: {e}")
            logger.error(f"[Oxylabs] Response: {e.response.text if e.response else 'No response'}")
            return None
        except Exception as e:
            logger.error(f"[Oxylabs] Scrape failed: {e}", exc_info=True)
            return None

    def search_google_shopping(
        self,
        query: str,
        max_price: Optional[float] = None,
        page: int = 1,
        geo_location: str = "United States"
    ) -> Optional[List[Dict]]:
        """
        Search Google Shopping using Oxylabs.

        Args:
            query: Product search query
            max_price: Optional maximum price filter
            page: Page number (default: 1)
            geo_location: Geographic location for results

        Returns:
            List of product results, or None if failed
        """
        logger.info(f"[Oxylabs] Google Shopping search: {query}")

        try:
            # Use google_shopping_search with query parameter (not url)
            # Oxylabs automatically handles filters like max_price via query string
            search_query = query
            if max_price:
                search_query += f" under ${int(max_price)}"

            payload = {
                "source": "google_shopping_search",
                "query": search_query,
                "domain": "com",
                "geo_location": geo_location,
                "parse": True,  # Let Oxylabs parse the results
                "start_page": page,
                "pages": 1
            }

            response = requests.post(
                self.base_url,
                auth=(self.username, self.password),
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30  # Reduced from 60s - correct API call should be fast
            )

            response.raise_for_status()
            data = response.json()

            logger.info(f"[Oxylabs] Response status: {response.status_code}")

            # Extract shopping results
            if 'results' in data and len(data['results']) > 0:
                result = data['results'][0]

                # Oxylabs parsed content
                if 'content' in result:
                    content = result['content']

                    # Check for organic results (products)
                    if isinstance(content, dict) and 'results' in content:
                        products = content['results'].get('organic', [])
                        logger.info(f"[Oxylabs] Found {len(products)} products")
                        return products
                    elif isinstance(content, dict) and 'organic' in content:
                        products = content['organic']
                        logger.info(f"[Oxylabs] Found {len(products)} products")
                        return products

                logger.warning(f"[Oxylabs] No products in parsed content")
                return []
            else:
                logger.warning(f"[Oxylabs] No results in response")
                return []

        except requests.exceptions.HTTPError as e:
            logger.error(f"[Oxylabs] HTTP error: {e}")
            if e.response:
                logger.error(f"[Oxylabs] Response: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"[Oxylabs] Search failed: {e}", exc_info=True)
            return None

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
        Search for products and transform to Elara Product model.

        This is the main entry point for product search - matches SearchAPI interface.

        Args:
            descriptor: Product description (e.g., "navy blazer", "white sneakers")
            price_max: Maximum price constraint
            location: User location for geo-targeting (unused)
            max_results: Maximum number of products to return
            prefer_new: Prefer new condition items (unused)
            prefer_free_delivery: Prefer items with free delivery (unused)

        Returns:
            List of Product objects
        """
        try:
            # Search via Oxylabs Google Shopping
            raw_products = self.search_google_shopping(
                query=descriptor,
                max_price=price_max,
                page=1
            )

            if not raw_products:
                logger.warning(f"[Oxylabs] No products found for: {descriptor}")
                return []

            # Convert to Product objects
            products = []
            for item in raw_products[:max_results]:
                product = self._raw_to_product(item)
                if product:
                    products.append(product)

            logger.info(f"[Oxylabs] Returning {len(products)} products")
            return products

        except Exception as e:
            logger.error(f"[Oxylabs] Product search failed for '{descriptor}': {type(e).__name__}: {str(e)}")
            logger.debug(f"[Oxylabs] Full error traceback:", exc_info=True)
            return []

    def _raw_to_product(self, item: Dict) -> Optional[Product]:
        """
        Convert raw Oxylabs product data to Product object.

        Args:
            item: Raw product dictionary from Oxylabs

        Returns:
            Product object or None if conversion fails
        """
        try:
            # Extract fields from Oxylabs google_shopping_search response
            title = item.get('title', '')

            # Price can be float or string
            price_value = item.get('price', 0)
            if isinstance(price_value, (int, float)):
                price = float(price_value)
            else:
                # Parse string price
                try:
                    price_clean = str(price_value).replace('$', '').replace(',', '').replace('USD', '').strip()
                    price = float(price_clean) if price_clean else 0.0
                except (ValueError, AttributeError):
                    logger.warning(f"[Oxylabs] Could not parse price: {price_value}")
                    price = 0.0

            # Extract merchant URL and name
            merchant = item.get('merchant', {})
            if isinstance(merchant, dict):
                link = merchant.get('url', '')
                retailer = merchant.get('name', 'Unknown')
            else:
                # Fallback to old format
                link = item.get('link', '')
                retailer = item.get('source', 'Unknown')

            # Skip if missing essential fields
            if not title or not link:
                logger.warning(f"[Oxylabs] Skipping product with missing title or link")
                return None

            # Create Product object
            product = Product(
                id=f"oxylabs_{uuid.uuid4().hex[:12]}",
                title=title,
                brand=retailer,
                category=None,  # Oxylabs doesn't provide category
                price=price,
                currency=item.get('currency', 'USD'),
                url=link,
                image=item.get('thumbnail', ''),
                retailer=retailer,
                color=None,
                size=None,
                material=None,
                rating=item.get('rating'),
                source="google_shopping"
            )

            return product

        except Exception as e:
            logger.error(f"[Oxylabs] Failed to convert product: {e}")
            return None

    def scrape_url(
        self,
        url: str
    ) -> Optional[Dict]:
        """
        Scrape a specific URL using Oxylabs universal source.

        Args:
            url: URL to scrape

        Returns:
            Scraped content and metadata
        """
        logger.info(f"[Oxylabs] Scraping URL: {url[:80]}...")

        try:
            payload = {
                "source": "universal",
                "url": url,
                "parse": False  # Get raw content
            }

            response = requests.post(
                self.base_url,
                auth=(self.username, self.password),
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            logger.info(f"[Oxylabs] Scraped URL successfully")
            return data

        except Exception as e:
            logger.error(f"[Oxylabs] Failed to scrape URL: {e}", exc_info=True)
            return None

# Test function
async def test_oxylabs():
    """Test Oxylabs retailer page scraping"""
    client = OxylabsClient()

    print("\\n" + "="*80)
    print("Testing Oxylabs Retailer Page Scraping")
    print("="*80)

    # Test scraping a Nordstrom category page
    test_url = "https://www.nordstrom.com/browse/women/shoes/heels"
    html = client.scrape_retailer_page(test_url)

    if html:
        print(f"\\nSuccessfully scraped {len(html)} bytes of HTML")
        print(f"First 200 chars: {html[:200]}...")
    else:
        print("\\nFailed to scrape page")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_oxylabs())
