"""
OpenSERP Client - Primary product search source using local OpenSERP server.

OpenSERP provides free Google, Bing, DuckDuckGo search results without API costs.
Running locally on port 7001 with all search engines initialized.

Features:
- Rate limiting to prevent server overload
- Automatic retry with exponential backoff
- Increased timeouts for stability
- Connection pooling for better performance
"""

import httpx
import logging
import asyncio
from typing import List, Dict, Optional
from urllib.parse import quote_plus


logger = logging.getLogger(__name__)


class ProductCandidate:
    """Represents a product found via OpenSERP"""

    def __init__(self, title: str, url: str, description: str, engine: str, rank: int):
        self.title = title
        self.url = url
        self.description = description
        self.engine = engine
        self.rank = rank

    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'url': self.url,
            'description': self.description,
            'engine': self.engine,
            'rank': self.rank
        }


class OpenSERPClient:
    """
    Client for OpenSERP local server with rate limiting and retry logic.

    OpenSERP provides access to multiple search engines:
    - Google (best for shopping)
    - Bing
    - DuckDuckGo
    - Yandex
    - Baidu
    """

    def __init__(
        self,
        base_url: str = "http://localhost:7001",
        max_concurrent_requests: int = 1,  # CRITICAL: OpenSERP crashes with >1 concurrent requests
        request_delay: float = 2.0  # Increased delay between requests to prevent crashes
    ):
        """
        Initialize OpenSERP client with rate limiting.

        Args:
            base_url: OpenSERP server URL (default: http://localhost:7001)
            max_concurrent_requests: Maximum concurrent requests to server (MUST be 1 to prevent crashes)
            request_delay: Minimum delay between requests in seconds
        """
        self.base_url = base_url
        self.timeout = 60.0  # Increased from 30s to 60s
        self.max_concurrent_requests = max_concurrent_requests
        self.request_delay = request_delay
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._last_request_time = 0.0
        logger.info(f"[OpenSERP] Initialized client for {base_url} (max_concurrent={max_concurrent_requests}, delay={request_delay}s)")

    async def search_products(
        self,
        query: str,
        max_results: int = 20,
        engines: Optional[List[str]] = None,
        max_retries: int = 3
    ) -> List[ProductCandidate]:
        """
        Search for products using OpenSERP with automatic retry.

        Args:
            query: Search query (e.g., "black leather heels women")
            max_results: Maximum number of results to return
            engines: List of engines to use (default: ["google", "bing", "duckduckgo"])
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            List of ProductCandidate objects
        """
        # Default to fast, reliable engines
        if engines is None:
            engines = ["google", "bing", "duckduckgo"]

        logger.info(f"[OpenSERP] Searching for: {query} (engines: {engines}, limit: {max_results})")

        # Retry loop with exponential backoff
        for attempt in range(max_retries):
            try:
                # CRITICAL FIX: Hold semaphore for ENTIRE request duration, not just rate limiting check
                async with self._semaphore:
                    # Enforce minimum delay between requests
                    current_time = asyncio.get_event_loop().time()
                    time_since_last = current_time - self._last_request_time
                    if time_since_last < self.request_delay:
                        await asyncio.sleep(self.request_delay - time_since_last)
                    self._last_request_time = asyncio.get_event_loop().time()

                    async with httpx.AsyncClient(
                        timeout=httpx.Timeout(self.timeout, connect=10.0),
                        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
                    ) as client:
                        # Use megasearch to query multiple engines at once
                        engines_param = ",".join(engines)
                        url = f"{self.base_url}/mega/search"
                        params = {
                            "text": query,
                            "engines": engines_param,
                            "limit": max_results
                        }

                        logger.debug(f"[OpenSERP] Attempt {attempt + 1}/{max_retries}: GET {url}")
                        response = await client.get(url, params=params)
                        response.raise_for_status()

                        results = response.json()
                        logger.info(f"[OpenSERP] Received {len(results)} results")

                        # Convert to ProductCandidate objects
                        products = []
                        for item in results:
                            if not isinstance(item, dict):
                                continue

                            # Skip ads
                            if item.get('ad', False):
                                continue

                            title = item.get('title', '')
                            url = item.get('url', '')
                            description = item.get('description', '')
                            engine = item.get('engine', 'unknown')
                            rank = item.get('rank', 0)

                            if not title or not url:
                                continue

                            products.append(ProductCandidate(
                                title=title,
                                url=url,
                                description=description,
                                engine=engine,
                                rank=rank
                            ))

                        logger.info(f"[OpenSERP] Extracted {len(products)} product candidates")
                        return products

            except httpx.TimeoutException as e:
                logger.warning(f"[OpenSERP] Timeout on attempt {attempt + 1}/{max_retries}: {query}")
                if attempt == max_retries - 1:
                    logger.error(f"[OpenSERP] All retries exhausted for: {query}")
                    return []
                # Exponential backoff: 1s, 2s, 4s
                await asyncio.sleep(2 ** attempt)

            except httpx.HTTPStatusError as e:
                logger.error(f"[OpenSERP] HTTP error {e.response.status_code}: {e}")
                return []  # Don't retry on HTTP errors

            except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as e:
                logger.warning(f"[OpenSERP] Connection error on attempt {attempt + 1}/{max_retries}: {type(e).__name__}")
                if attempt == max_retries - 1:
                    logger.error(f"[OpenSERP] All retries exhausted for: {query}")
                    return []
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)

            except Exception as e:
                logger.error(f"[OpenSERP] Unexpected error searching: {e}", exc_info=True)
                return []

        return []

    async def check_health(self) -> bool:
        """
        Check if OpenSERP server is healthy and engines are initialized.

        Returns:
            True if server is healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/mega/engines")
                response.raise_for_status()
                data = response.json()

                # Check that all engines are initialized
                engines = data.get('engines', [])
                initialized_count = sum(1 for e in engines if e.get('initialized', False))
                total = data.get('total', 0)

                logger.info(f"[OpenSERP] Health check: {initialized_count}/{total} engines initialized")
                return initialized_count > 0

        except Exception as e:
            logger.error(f"[OpenSERP] Health check failed: {e}")
            return False


# Test function
async def test_openserp():
    """Test the OpenSERP client"""
    client = OpenSERPClient()

    # Health check
    healthy = await client.check_health()
    print(f"\n✓ OpenSERP health check: {'PASS' if healthy else 'FAIL'}")

    if not healthy:
        print("\n❌ OpenSERP server not healthy. Make sure it's running on port 7001:")
        print("   cd /path/to/openserp && ./openserp serve -a 0.0.0.0 -p 7001")
        return

    # Search for products
    products = await client.search_products(
        query="black leather heels women",
        max_results=10
    )

    print(f"\n✓ Found {len(products)} products via OpenSERP:")
    for i, p in enumerate(products, 1):
        print(f"\n{i}. {p.title}")
        print(f"   URL: {p.url[:80]}...")
        print(f"   Engine: {p.engine}")
        print(f"   Description: {p.description[:100]}...")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_openserp())
