"""
Stage A: Google Shopping Harvester (Selenium-based)
====================================================

Lightweight scraper that harvests candidate products from Google Shopping.
Returns first-party PDP URLs without heavy browser verification.

Key Features:
- Scrapes Google Shopping for product cards
- Resolves Google redirect links to real retailer URLs
- Filters to whitelisted retailers only
- Returns ~20 candidate URLs for further filtering

Author: Elara Team
"""

import asyncio
import re
import httpx
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs
import logging
try:
    import undetected_chromedriver as uc
    HAS_UNDETECTED_CHROME = True
except ImportError:
    HAS_UNDETECTED_CHROME = False
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

logger = logging.getLogger(__name__)


@dataclass
class ProductCandidate:
    """Raw product candidate from Google Shopping"""
    title: str
    retailer_name: str
    retailer_domain: str
    google_link: str
    pdp_url: Optional[str] = None  # Resolved first-party URL
    price: Optional[float] = None
    image_url: Optional[str] = None
    product_id: Optional[str] = None


class GoogleShoppingHarvester:
    """
    Harvest product candidates from Google Shopping using Selenium.

    This is Stage A of the multi-stage filtering pipeline.
    Goal: Get 20 candidate URLs quickly without heavy verification.
    """

    # Whitelisted retailers (first-party only)
    RETAILER_WHITELIST = {
        'nordstrom.com', 'macys.com', 'zara.com', 'hm.com',
        'asos.com', 'shopbop.com', 'revolve.com', 'ssense.com',
        'net-a-porter.com', 'farfetch.com', 'bloomingdales.com',
        'saksfifthavenue.com', 'neimanmarcus.com', 'bergdorfgoodman.com',
        'anthropologie.com', 'urbanoutfitters.com', 'freepeople.com',
        'jcrew.com', 'bananarepublic.com', 'gap.com',
        'target.com', 'walmart.com', 'kohls.com'
    }

    # Blacklist (aggregators, redirectors, marketplaces)
    RETAILER_BLACKLIST = {
        'amazon.com', 'ebay.com', 'etsy.com', 'poshmark.com',
        'mercari.com', 'depop.com', 'grailed.com', 'thredup.com',
        'therealreal.com', 'vestiairecollective.com'
    }

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 10,
        max_candidates: int = 20,
        user_agent: Optional[str] = None
    ):
        """
        Initialize Google Shopping harvester.

        Args:
            headless: Run browser in headless mode
            timeout: Page load timeout in seconds
            max_candidates: Maximum candidates to return
            user_agent: Custom user agent string
        """
        self.headless = headless
        self.timeout = timeout
        self.max_candidates = max_candidates
        self.user_agent = user_agent or (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )
        self._driver = None

    def _create_driver(self):
        """Create Chrome driver with advanced anti-detection settings"""
        if HAS_UNDETECTED_CHROME:
            # Use undetected-chromedriver (bypasses most bot detection)
            logger.info("[Harvester] Using undetected-chromedriver for better anti-detection")
            options = uc.ChromeOptions()

            if self.headless:
                options.add_argument('--headless=new')

            # Performance settings
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions')

            driver = uc.Chrome(options=options, version_main=None)
            driver.set_page_load_timeout(self.timeout)

            return driver
        else:
            # Fallback to regular Selenium
            logger.warning("[Harvester] undetected-chromedriver not available, using regular Selenium")
            from selenium.webdriver.chrome.options import Options
            chrome_options = Options()

            if self.headless:
                chrome_options.add_argument('--headless=new')

            # Anti-detection settings
            chrome_options.add_argument(f'user-agent={self.user_agent}')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            # Performance settings
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-images')

            from selenium import webdriver
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(self.timeout)

            # Remove webdriver property
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            return driver

    async def harvest(
        self,
        query: str,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None
    ) -> List[ProductCandidate]:
        """
        Harvest product candidates from Google Shopping.

        Args:
            query: Search query (e.g., "black heels women")
            max_price: Maximum price filter
            min_price: Minimum price filter

        Returns:
            List of ProductCandidate objects (up to max_candidates)
        """
        try:
            logger.info(f"[Harvester] Searching Google Shopping: {query}")

            # Build Google Shopping URL
            url = self._build_search_url(query, max_price, min_price)

            # Create driver
            self._driver = self._create_driver()

            # Load search results
            self._driver.get(url)

            # Wait for product cards to load
            await asyncio.sleep(2)  # Give time for JS to render

            # Extract product cards
            candidates = await self._extract_product_cards()

            # Filter by whitelist/blacklist
            candidates = self._filter_retailers(candidates)

            # Resolve Google redirect links to real URLs
            candidates = await self._resolve_redirects(candidates)

            # Deduplicate by domain + normalized title
            candidates = self._deduplicate(candidates)

            logger.info(
                f"[Harvester] Found {len(candidates)} valid candidates "
                f"from {len(set(c.retailer_domain for c in candidates))} retailers"
            )

            return candidates[:self.max_candidates]

        except TimeoutException:
            logger.error(f"[Harvester] Timeout loading Google Shopping for: {query}")
            return []
        except Exception as e:
            logger.error(f"[Harvester] Error: {type(e).__name__}: {str(e)}")
            return []
        finally:
            if self._driver:
                self._driver.quit()
                self._driver = None

    def _build_search_url(
        self,
        query: str,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None
    ) -> str:
        """Build Google Shopping search URL with filters"""
        base_url = "https://www.google.com/search"

        # Add price filter to query
        if max_price:
            query += f" under ${int(max_price)}"

        params = {
            'q': query,
            'tbm': 'shop',  # Shopping tab
            'hl': 'en',
            'gl': 'us'
        }

        # Build URL manually (avoid encoding issues)
        param_str = '&'.join(f"{k}={v.replace(' ', '+')}" for k, v in params.items())
        return f"{base_url}?{param_str}"

    async def _extract_product_cards(self) -> List[ProductCandidate]:
        """Extract product cards from Google Shopping results page"""
        candidates = []

        try:
            # Wait for product grid
            WebDriverWait(self._driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-docid]'))
            )

            # Find all product cards
            # Google Shopping uses data-docid attribute for product cards
            product_cards = self._driver.find_elements(By.CSS_SELECTOR, 'div[data-docid]')

            logger.info(f"[Harvester] Found {len(product_cards)} product cards")

            for card in product_cards[:40]:  # Process top 40 cards
                try:
                    candidate = self._parse_product_card(card)
                    if candidate:
                        candidates.append(candidate)
                except Exception as e:
                    logger.debug(f"[Harvester] Error parsing card: {e}")
                    continue

            return candidates

        except TimeoutException:
            logger.warning("[Harvester] No product cards found (timeout)")
            return []
        except Exception as e:
            logger.error(f"[Harvester] Error extracting cards: {e}")
            return []

    def _parse_product_card(self, card) -> Optional[ProductCandidate]:
        """Parse individual product card to extract metadata"""
        try:
            # Extract product title
            title_elem = card.find_element(By.CSS_SELECTOR, 'h3, h4, [role="heading"]')
            title = title_elem.text.strip()

            if not title:
                return None

            # Extract retailer info (usually in a merchant/seller element)
            retailer_name = "Unknown"
            retailer_domain = None

            try:
                # Common selectors for retailer name
                seller_elem = card.find_element(By.CSS_SELECTOR, '[data-sh-seller], .merchant-name, .aULzUe')
                retailer_name = seller_elem.text.strip()
            except NoSuchElementException:
                pass

            # Extract link (Google redirect link)
            link_elem = card.find_element(By.CSS_SELECTOR, 'a[href*="/shopping/product/"]')
            google_link = link_elem.get_attribute('href')

            # Try to extract domain from link or merchant info
            if google_link:
                # Parse domain from Google Shopping link
                parsed = urlparse(google_link)
                if 'url' in parse_qs(parsed.query):
                    target_url = parse_qs(parsed.query)['url'][0]
                    retailer_domain = urlparse(target_url).netloc.lower().replace('www.', '')

            # Extract price
            price = None
            try:
                price_elem = card.find_element(By.CSS_SELECTOR, '[data-sh-price], .price, .a8Pemb')
                price_text = price_elem.text.strip()
                price = self._parse_price(price_text)
            except NoSuchElementException:
                pass

            # Extract image
            image_url = None
            try:
                img_elem = card.find_element(By.CSS_SELECTOR, 'img')
                image_url = img_elem.get_attribute('src')
            except NoSuchElementException:
                pass

            # Extract product ID from data-docid
            product_id = card.get_attribute('data-docid')

            return ProductCandidate(
                title=title,
                retailer_name=retailer_name,
                retailer_domain=retailer_domain or "unknown.com",
                google_link=google_link,
                price=price,
                image_url=image_url,
                product_id=product_id
            )

        except Exception as e:
            logger.debug(f"[Harvester] Error parsing card: {e}")
            return None

    def _parse_price(self, price_text: str) -> Optional[float]:
        """Parse price string to float"""
        try:
            # Remove currency symbols and commas
            price_clean = re.sub(r'[^\d.]', '', price_text)
            return float(price_clean)
        except (ValueError, AttributeError):
            return None

    def _filter_retailers(self, candidates: List[ProductCandidate]) -> List[ProductCandidate]:
        """Filter candidates by retailer whitelist/blacklist"""
        filtered = []

        for candidate in candidates:
            domain = candidate.retailer_domain

            # Check blacklist first
            if any(blocked in domain for blocked in self.RETAILER_BLACKLIST):
                logger.debug(f"[Harvester] Blacklisted retailer: {domain}")
                continue

            # Check whitelist
            if any(allowed in domain for allowed in self.RETAILER_WHITELIST):
                filtered.append(candidate)
            else:
                logger.debug(f"[Harvester] Non-whitelisted retailer: {domain}")

        return filtered

    async def _resolve_redirects(self, candidates: List[ProductCandidate]) -> List[ProductCandidate]:
        """Resolve Google redirect links to actual retailer URLs"""
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=5,
            headers={'User-Agent': self.user_agent}
        ) as client:

            tasks = []
            for candidate in candidates:
                tasks.append(self._resolve_single_redirect(client, candidate))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            resolved = []
            for result in results:
                if isinstance(result, ProductCandidate) and result.pdp_url:
                    resolved.append(result)

            return resolved

    async def _resolve_single_redirect(
        self,
        client: httpx.AsyncClient,
        candidate: ProductCandidate
    ) -> ProductCandidate:
        """Resolve single Google redirect to retailer URL"""
        try:
            response = await client.head(candidate.google_link, follow_redirects=True)
            final_url = str(response.url)

            # Verify domain matches
            final_domain = urlparse(final_url).netloc.lower().replace('www.', '')
            if final_domain != candidate.retailer_domain:
                logger.debug(f"[Harvester] Domain mismatch: {final_domain} != {candidate.retailer_domain}")
                candidate.retailer_domain = final_domain

            candidate.pdp_url = final_url
            return candidate

        except Exception as e:
            logger.debug(f"[Harvester] Error resolving redirect: {e}")
            return candidate

    def _deduplicate(self, candidates: List[ProductCandidate]) -> List[ProductCandidate]:
        """Deduplicate by domain + normalized title"""
        seen: Set[str] = set()
        unique = []

        for candidate in candidates:
            # Create dedup key
            title_normalized = re.sub(r'[^\w\s]', '', candidate.title.lower())
            title_normalized = ' '.join(title_normalized.split())  # Normalize whitespace
            key = f"{candidate.retailer_domain}:{title_normalized}"

            if key not in seen:
                seen.add(key)
                unique.append(candidate)

        return unique


# Convenience function for one-off searches
async def harvest_google_shopping(
    query: str,
    max_price: Optional[float] = None,
    max_candidates: int = 20,
    headless: bool = True
) -> List[ProductCandidate]:
    """
    Quick harvest from Google Shopping.

    Args:
        query: Search query
        max_price: Maximum price filter
        max_candidates: Maximum results to return
        headless: Run browser in headless mode

    Returns:
        List of ProductCandidate objects
    """
    harvester = GoogleShoppingHarvester(
        headless=headless,
        max_candidates=max_candidates
    )
    return await harvester.harvest(query, max_price=max_price)
