"""
Visual Shopping Scraper - Extracts product data from Google Shopping using screenshots + AI vision.

This approach is more robust than CSS selectors because it:
1. Works regardless of HTML structure changes
2. Extracts data the same way humans see it
3. Can handle dynamically loaded content
4. More resilient to Google's anti-scraping measures

Uses Playwright for browser control and Claude Vision for data extraction.
"""

import base64
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path
import openai
import os


logger = logging.getLogger(__name__)


class ProductCandidate:
    """Represents a product found via visual scraping"""

    def __init__(self, title: str, price: str, url: str, retailer: Optional[str] = None, image_url: Optional[str] = None):
        self.title = title
        self.price = price
        self.url = url
        self.retailer = retailer
        self.image_url = image_url

    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'price': self.price,
            'url': self.url,
            'retailer': self.retailer,
            'image_url': self.image_url
        }


class VisualShoppingScraper:
    """
    Visual scraper that uses Playwright + GPT-4 Vision to extract product data from screenshots.

    This is a fallback approach when traditional CSS selectors fail due to:
    - Frequent HTML structure changes
    - Heavily obfuscated class names
    - JavaScript-rendered content
    """

    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize visual scraper.

        Args:
            openai_api_key: OpenAI API key for GPT-4 Vision. Falls back to OPENAI_API_KEY env var.
        """
        self.api_key = openai_api_key or os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key required for visual scraping. Set OPENAI_API_KEY env var.")

        self.client = openai.OpenAI(api_key=self.api_key)
        logger.info("[VisualScraper] Initialized with GPT-4 Vision")

    async def scrape_google_shopping(
        self,
        query: str,
        max_results: int = 20,
        max_price: Optional[float] = None
    ) -> List[ProductCandidate]:
        """
        Scrape Google Shopping using visual approach.

        Args:
            query: Search query (e.g., "black leather heels women")
            max_results: Maximum number of products to return
            max_price: Optional price filter

        Returns:
            List of ProductCandidate objects
        """
        from playwright.async_api import async_playwright

        logger.info(f"[VisualScraper] Starting visual scrape for query: {query}")

        # Build Google Shopping URL
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=shop&hl=en&gl=us"
        if max_price:
            url += f"&tbs=mr:1,price:1,ppr_max:{int(max_price)}"

        async with async_playwright() as p:
            # Launch browser (non-headless for better success rate)
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 1400},  # Taller viewport to capture more products
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            page = await context.new_page()

            try:
                # Navigate to Google Shopping
                logger.info(f"[VisualScraper] Navigating to: {url}")
                await page.goto(url, wait_until='networkidle', timeout=30000)

                # Scroll to load products
                await page.evaluate('window.scrollTo(0, 800)')
                await page.wait_for_timeout(2000)

                # Take screenshot
                screenshot_bytes = await page.screenshot(full_page=False)
                screenshot_b64 = base64.standard_b64encode(screenshot_bytes).decode('utf-8')

                logger.info(f"[VisualScraper] Screenshot captured ({len(screenshot_bytes)} bytes)")

                # Extract products using Claude Vision
                products = await self._extract_products_from_screenshot(screenshot_b64, query, max_results)

                logger.info(f"[VisualScraper] Extracted {len(products)} products via AI vision")

                return products

            finally:
                await browser.close()

    async def _extract_products_from_screenshot(
        self,
        screenshot_b64: str,
        query: str,
        max_results: int
    ) -> List[ProductCandidate]:
        """
        Use Claude Vision to extract product data from screenshot.

        Args:
            screenshot_b64: Base64-encoded screenshot
            query: Original search query for context
            max_results: Maximum number of products to extract

        Returns:
            List of ProductCandidate objects
        """
        prompt = f"""You are analyzing a screenshot of Google Shopping search results for the query: "{query}"

Please extract product information from the visible product cards in the image. For each product, identify:
1. Product title/name
2. Price (as shown, e.g., "$89.99" or "$120.00")
3. Retailer/merchant name (e.g., "Nordstrom", "Macy's", "DSW")

Return the results as a JSON array with up to {max_results} products. Use this exact format:

[
  {{
    "title": "Product Name Here",
    "price": "$XX.XX",
    "retailer": "Retailer Name"
  }},
  ...
]

IMPORTANT:
- Only extract products that are clearly visible in the screenshot
- Do NOT make up or invent products
- If you can't read a field clearly, use null
- Skip filter chips, ads, or non-product elements
- Focus on the main product grid/carousel

Return ONLY the JSON array, no other text."""

        try:
            # Call GPT-4 Vision API
            response = self.client.chat.completions.create(
                model="gpt-4o",  # GPT-4 with vision support
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_b64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }]
            )

            # Parse response
            response_text = response.choices[0].message.content
            logger.debug(f"[VisualScraper] GPT response: {response_text[:200]}...")

            # Extract JSON from response
            products_data = self._parse_json_response(response_text)

            # Convert to ProductCandidate objects
            products = []
            for item in products_data:
                if not isinstance(item, dict):
                    continue

                title = item.get('title')
                price = item.get('price')
                retailer = item.get('retailer')

                if not title or not price:
                    continue

                # Note: We don't have direct product URLs from visual scraping
                # Will need to construct search URLs or do a secondary lookup
                url = f"https://www.google.com/search?q={title.replace(' ', '+')}+{retailer or ''}&tbm=shop"

                products.append(ProductCandidate(
                    title=title,
                    price=price,
                    url=url,
                    retailer=retailer
                ))

            return products

        except openai.OpenAIError as e:
            logger.error(f"[VisualScraper] OpenAI API error: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"[VisualScraper] Error extracting products from screenshot: {e}", exc_info=True)
            return []

    def _parse_json_response(self, response_text: str) -> List[Dict]:
        """
        Parse JSON from GPT's response, handling various formats.

        Args:
            response_text: Raw response text from GPT

        Returns:
            List of product dictionaries
        """
        try:
            # Try direct JSON parse
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if '```json' in response_text:
                start = response_text.find('```json') + 7
                end = response_text.find('```', start)
                json_str = response_text[start:end].strip()
                return json.loads(json_str)
            elif '```' in response_text:
                start = response_text.find('```') + 3
                end = response_text.find('```', start)
                json_str = response_text[start:end].strip()
                return json.loads(json_str)
            else:
                # Try to find JSON array in text
                start = response_text.find('[')
                end = response_text.rfind(']') + 1
                if start >= 0 and end > start:
                    json_str = response_text[start:end]
                    return json.loads(json_str)

        logger.warning(f"[VisualScraper] Could not parse JSON from response: {response_text[:200]}")
        return []


# Test function
async def test_visual_scraper():
    """Test the visual scraper"""
    scraper = VisualShoppingScraper()

    products = await scraper.scrape_google_shopping(
        query="black leather heels women",
        max_results=10,
        max_price=150
    )

    print(f"\n✓ Found {len(products)} products via visual scraping:")
    for i, p in enumerate(products, 1):
        print(f"\n{i}. {p.title}")
        print(f"   Price: {p.price}")
        print(f"   Retailer: {p.retailer}")
        print(f"   URL: {p.url[:80]}...")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_visual_scraper())
