"""
Claude Web Search Client - Uses Claude's web search capabilities for product enrichment.

Claude can perform web searches and extract structured product information including:
- Product titles
- Prices
- Direct buy links
- Retailer information
- Product images

This provides better accuracy than scraping because Claude can understand context
and extract the exact product URLs from search results.
"""

import anthropic
import logging
import json
from typing import List, Dict, Optional
import config


logger = logging.getLogger(__name__)


class ProductCandidate:
    """Represents a product found via Claude web search"""

    def __init__(
        self,
        title: str,
        url: str,
        price: Optional[float] = None,
        currency: str = "USD",
        retailer: Optional[str] = None,
        image_url: Optional[str] = None,
        description: Optional[str] = None
    ):
        self.title = title
        self.url = url
        self.price = price
        self.currency = currency
        self.retailer = retailer
        self.image_url = image_url
        self.description = description

    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'url': self.url,
            'price': self.price,
            'currency': self.currency,
            'retailer': self.retailer,
            'image_url': self.image_url,
            'description': self.description
        }


class ClaudeWebSearchClient:
    """
    Client for Claude web search with product extraction.

    Uses Claude's ability to search the web and extract structured product data
    from shopping sites. More accurate than traditional scraping because Claude
    can understand product pages and extract exact buy links.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Initialize Claude web search client.

        Args:
            api_key: Anthropic API key (falls back to config.ANTHROPIC_API_KEY)
            base_url: API base URL (falls back to config.ANTHROPIC_BASE_URL)
            model: Model to use (falls back to config.ANTHROPIC_SMALL_FAST_MODEL)
        """
        self.api_key = api_key or config.ANTHROPIC_API_KEY
        self.base_url = base_url or config.ANTHROPIC_BASE_URL
        self.model = model or config.ANTHROPIC_SMALL_FAST_MODEL

        if not self.api_key:
            raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY env var.")

        # Initialize Anthropic client
        self.client = anthropic.Anthropic(
            api_key=self.api_key,
            base_url=self.base_url
        )

        logger.info(f"[ClaudeWebSearch] Initialized with model: {self.model}")

    async def search_products(
        self,
        query: str,
        max_results: int = 20,
        max_price: Optional[float] = None,
        preferred_retailers: Optional[List[str]] = None
    ) -> List[ProductCandidate]:
        """
        Search for products using multi-retailer direct search strategy.

        Strategy:
        1. Search specific US retailer sites using site: operator
        2. Get product pages from Nordstrom, Zara, H&M, ASOS, Macy's
        3. Use Claude to extract structured product info

        Args:
            query: Product search query (e.g., "black leather heels women")
            max_results: Maximum number of products to return
            max_price: Optional maximum price filter
            preferred_retailers: Optional list of preferred retailers

        Returns:
            List of ProductCandidate objects
        """
        logger.info(f"[ClaudeWebSearch] Searching US retailers for: {query}")

        try:
            from ddgs import DDGS

            # Target US retailers with specific search patterns
            search_patterns = [
                f"{query} site:nordstrom.com/s/",  # Nordstrom product pages
                f"{query} site:zara.com/us/",      # Zara US
                f"{query} site:hm.com/en_us/",      # H&M US
                f"{query} site:asos.com/us/",       # ASOS US
                f"{query} site:macys.com/shop/product/",  # Macy's products
            ]

            search_results = []
            ddg = DDGS()

            # Try each search pattern
            for search_pattern in search_patterns:
                if len(search_results) >= max_results:
                    break

                logger.info(f"[ClaudeWebSearch] Searching: {search_pattern}...")

                try:
                    count = 0
                    for result in ddg.text(search_pattern, region='us-en', max_results=5):
                        link = result.get('href', '')

                        # Filter out international domains
                        intl_patterns = ['.in/', '.au/', '.uk/', '.ca/', '.eu/', '.de/', '.fr/', '.es/', '.it/']
                        if any(pattern in link.lower() for pattern in intl_patterns):
                            continue

                        # For category pages, still include them - Claude can handle them
                        search_results.append({
                            'title': result.get('title', ''),
                            'link': link,
                            'snippet': result.get('body', '')
                        })
                        count += 1

                        if len(search_results) >= max_results:
                            break

                    logger.info(f"[ClaudeWebSearch] Found {count} results from this search")

                except Exception as e:
                    logger.warning(f"[ClaudeWebSearch] Search failed: {e}")
                    continue

            logger.info(f"[ClaudeWebSearch] Found {len(search_results)} total product pages")

            if not search_results:
                logger.warning(f"[ClaudeWebSearch] No products found across retailers")
                return []

            # Step 2: Use Claude to extract structured product info
            extraction_prompt = self._build_extraction_prompt(
                query, search_results[:max_results], max_price, preferred_retailers
            )

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                system="You are a shopping data extraction assistant. Extract structured product information from search results.",
                messages=[
                    {
                        "role": "user",
                        "content": extraction_prompt
                    }
                ]
            )

            # Extract product data from response
            content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text

            if not content:
                logger.warning(f"[ClaudeWebSearch] No content in Claude response")
                return []

            products = self._parse_product_response(content)

            logger.info(f"[ClaudeWebSearch] Extracted {len(products)} products")
            return products[:max_results]  # Limit to requested max_results

        except Exception as e:
            logger.error(f"[ClaudeWebSearch] Search failed: {e}", exc_info=True)
            return []

    def _build_extraction_prompt(
        self,
        query: str,
        search_results: List[Dict],
        max_price: Optional[float],
        preferred_retailers: Optional[List[str]]
    ) -> str:
        """Build prompt to extract product info from search results"""

        price_constraint = f" under ${max_price}" if max_price else ""
        retailer_pref = ""
        if preferred_retailers:
            retailer_pref = f"\n- Prefer products from: {', '.join(preferred_retailers)}"

        # Format search results
        results_text = "\n\n".join([
            f"Result {i+1}:\nTitle: {r['title']}\nURL: {r['link']}\nSnippet: {r['snippet']}"
            for i, r in enumerate(search_results)
        ])

        prompt = f"""I searched for "{query}"{price_constraint} and found these results:

{results_text}

Please extract up to 20 buyable products from these search results.

For each product, extract:
1. Product title/name (from the title or snippet)
2. Price (extract from snippet if mentioned, otherwise null)
3. Currency (MUST be USD - only include US retailer products)
4. Direct buy link (the URL provided)
5. Retailer name (extract from URL domain, e.g., "nordstrom.com" -> "Nordstrom")
6. Product image URL (null if not available)
7. Brief description (from snippet){retailer_pref}

CRITICAL REQUIREMENTS:
- All results are from trusted US retailers (Nordstrom, Zara, H&M, ASOS, Macy's, etc.)
- All prices should be in USD
- These are actual product pages from site-specific searches
- Extract product title, price (if visible), retailer name from URL
- Set price to null if not visible in snippet, but DO include the product

Return the results as a JSON array in this format:
[
  {{
    "title": "Product Name",
    "price": 89.99,
    "currency": "USD",
    "url": "https://retailer.com/product-page",
    "retailer": "Retailer Name",
    "image_url": null,
    "description": "Brief description from snippet"
  }},
  ...
]

Return ONLY the JSON array, no additional text. If no valid US retailer products found, return empty array []."""

        return prompt

    def _build_search_prompt(
        self,
        query: str,
        max_results: int,
        max_price: Optional[float],
        preferred_retailers: Optional[List[str]]
    ) -> str:
        """Build the search prompt for Claude"""

        price_constraint = f" under ${max_price}" if max_price else ""
        retailer_pref = ""
        if preferred_retailers:
            retailer_pref = f"\n- Prefer products from: {', '.join(preferred_retailers)}"

        prompt = f"""Please search the web for "{query}"{price_constraint} and find up to {max_results} buyable products from online fashion retailers.

For each product, extract:
1. Product title/name
2. Price (as a number, e.g., 89.99)
3. Currency (USD, EUR, etc.)
4. Direct buy link (the exact URL to purchase)
5. Retailer name (e.g., "Nordstrom", "ASOS", "Zara")
6. Product image URL (if available)
7. Brief description{retailer_pref}

IMPORTANT:
- Only include real, buyable products with working buy links
- Verify the URLs lead to actual product pages, not search results
- Extract the exact product price shown on the page
- Focus on well-known fashion retailers

Return the results as a JSON array in this format:
[
  {{
    "title": "Product Name",
    "price": 89.99,
    "currency": "USD",
    "url": "https://retailer.com/product-page",
    "retailer": "Retailer Name",
    "image_url": "https://...",
    "description": "Brief description"
  }},
  ...
]

Return ONLY the JSON array, no additional text."""

        return prompt

    def _parse_product_response(self, response_text: str) -> List[ProductCandidate]:
        """
        Parse product data from Claude's response.

        Args:
            response_text: Raw response text from Claude

        Returns:
            List of ProductCandidate objects
        """
        try:
            # Try direct JSON parse
            products_data = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if '```json' in response_text:
                start = response_text.find('```json') + 7
                end = response_text.find('```', start)
                json_str = response_text[start:end].strip()
                products_data = json.loads(json_str)
            elif '```' in response_text:
                start = response_text.find('```') + 3
                end = response_text.find('```', start)
                json_str = response_text[start:end].strip()
                products_data = json.loads(json_str)
            else:
                # Try to find JSON array in text
                start = response_text.find('[')
                end = response_text.rfind(']') + 1
                if start >= 0 and end > start:
                    json_str = response_text[start:end]
                    products_data = json.loads(json_str)
                else:
                    logger.warning(f"[ClaudeWebSearch] Could not parse JSON from response: {response_text[:200]}")
                    return []

        # Convert to ProductCandidate objects
        products = []
        for item in products_data:
            if not isinstance(item, dict):
                continue

            title = item.get('title')
            url = item.get('url')
            price = item.get('price')
            currency = item.get('currency', 'USD')
            retailer = item.get('retailer')
            image_url = item.get('image_url')
            description = item.get('description')

            if not title or not url:
                continue

            # Convert price to float if it's a string
            if isinstance(price, str):
                try:
                    # Remove currency symbols and commas
                    price_clean = price.replace('$', '').replace('₹', '').replace(',', '').strip()
                    price = float(price_clean)
                except (ValueError, AttributeError):
                    price = None

            products.append(ProductCandidate(
                title=title,
                url=url,
                price=price,
                currency=currency,
                retailer=retailer,
                image_url=image_url,
                description=description
            ))

        return products


# Test function
async def test_claude_web_search():
    """Test the Claude web search client"""
    client = ClaudeWebSearchClient()

    products = await client.search_products(
        query="black leather heels women",
        max_results=10,
        max_price=150
    )

    print(f"\n✓ Found {len(products)} products via Claude web search:")
    for i, p in enumerate(products, 1):
        print(f"\n{i}. {p.title}")
        print(f"   Price: ${p.price} {p.currency}")
        print(f"   Retailer: {p.retailer}")
        print(f"   URL: {p.url[:80]}...")
        if p.image_url:
            print(f"   Image: {p.image_url[:80]}...")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_claude_web_search())
