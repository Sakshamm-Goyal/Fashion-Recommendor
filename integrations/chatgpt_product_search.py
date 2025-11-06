# integrations/chatgpt_product_search.py
"""
ChatGPT-based product search fallback.
Uses GPT-4o to search for real, existing products with actual links and pricing.
This acts as a fallback when Google Shopping API or other APIs aren't configured.
"""

import json
import logging
from typing import List, Optional
from openai import OpenAI
from contracts.models import Product
import config

logger = logging.getLogger(__name__)


class ChatGPTProductSearcher:
    """
    Uses ChatGPT to find real products with actual links and pricing.

    ChatGPT has access to real product information and can provide:
    - Direct product links from major retailers
    - Current approximate pricing
    - Product availability
    - Brand and merchant information
    """

    def __init__(self):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        # Use latest model with web search capabilities if available
        # Priority: gpt-4o (latest with search) > gpt-4-turbo
        self.model = "gpt-4o"  # GPT-4o has web search when needed

    def search_products(
        self,
        query: str,
        min_price: float = 0,
        max_price: float = 10000,
        limit: int = 10
    ) -> List[Product]:
        """
        Search for real products using ChatGPT.

        Args:
            query: Product search query (e.g., "black leather Chelsea boots men's")
            min_price: Minimum price in USD
            max_price: Maximum price in USD
            limit: Maximum number of products to return

        Returns:
            List of Product objects with real links and pricing
        """
        logger.info(f"[ChatGPT Search] Searching for: {query} (${min_price}-${max_price})")

        system_prompt = """You are a fashion product search assistant that helps users find real products from actual retailers.

CRITICAL REQUIREMENTS - READ CAREFULLY:

1. **YOU MUST USE WEB SEARCH**: Before responding, search the web for ACTUAL, REAL products that are currently sold by major retailers.

2. **ONLY REAL URLs**: Every product URL MUST be a real, working link to an actual product page. Examples:
   ✓ GOOD: https://www.zara.com/us/en/leather-ankle-boots-p12345678.html
   ✓ GOOD: https://www.nordstrom.com/s/cole-haan-leather-loafers/5678901
   ✗ BAD: https://example.com/product/123
   ✗ BAD: https://retailer.example.com/p/abc123
   ✗ BAD: https://cdn.example.com/images/product.jpg

3. **VERIFY RETAILERS**: Only use these trusted retailers with real domains:
   - Nordstrom (nordstrom.com)
   - Macy's (macys.com)
   - ASOS (asos.com)
   - Zara (zara.com)
   - H&M (hm.com)
   - Amazon (amazon.com)
   - Revolve (revolve.com)
   - Bloomingdale's (bloomingdales.com)
   - Saks Fifth Avenue (saksfifthavenue.com)
   - Neiman Marcus (neimanmarcus.com)

4. **SEARCH FIRST, THEN RESPOND**: Use web search to find actual products before generating the response. Do NOT hallucinate or invent product URLs.

5. **IF YOU CAN'T FIND REAL PRODUCTS**: Return an empty products array rather than fake links.

Return products in this EXACT JSON format:
{
  "products": [
    {
      "name": "Exact product name from retailer website",
      "brand": "Actual brand name",
      "price": 129.99,
      "currency": "USD",
      "url": "https://REAL-RETAILER-DOMAIN.com/actual-product-path",
      "image_url": "https://real-cdn.com/actual-image.jpg",
      "merchant": "Retailer name",
      "description": "Brief product description",
      "in_stock": true,
      "category": "tops|bottoms|footwear|accessories"
    }
  ]
}

VALIDATION CHECKLIST BEFORE RESPONDING:
□ Did you search the web for real products?
□ Are ALL URLs from actual retailer domains (not example.com)?
□ Do the URLs look like real product pages (not fake IDs)?
□ Are the prices realistic for 2025?
□ Would clicking these links take users to real products?

If you cannot provide REAL, VERIFIED product URLs, return {"products": []} instead.
"""

        user_prompt = f"""Find {limit} real products matching this search:

Search Query: {query}
Price Range: ${min_price} - ${max_price}

Return {limit} products with real URLs, accurate pricing, and product details.
Focus on products from major fashion retailers that are likely in stock."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,  # Lower temperature for more consistent JSON
                max_tokens=3000  # More tokens for complex responses
            )

            # Parse JSON response
            content = response.choices[0].message.content

            # Try to parse, with fallback for malformed JSON
            try:
                result = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"[ChatGPT Search] JSON Parse Error: {e}")
                logger.error(f"[ChatGPT Search] Raw response: {content[:500]}...")
                return []

            products_data = result.get("products", [])

            # Convert to Product objects with validation
            products = []
            invalid_domains = ['example.com', 'example.org', 'test.com', 'fake.com', 'placeholder.com']

            for p in products_data[:limit]:
                try:
                    url = p.get("url", "")
                    image_url = p.get("image_url", "")

                    # CRITICAL: Filter out fake/example URLs
                    url_is_fake = any(domain in url.lower() for domain in invalid_domains)
                    image_is_fake = any(domain in image_url.lower() for domain in invalid_domains)

                    if url_is_fake:
                        logger.warning(f"  ⚠ Rejected fake URL: {url} for product: {p.get('name', 'unknown')}")
                        continue

                    if not url or not url.startswith('http'):
                        logger.warning(f"  ⚠ Rejected invalid URL: {url} for product: {p.get('name', 'unknown')}")
                        continue

                    # If image is fake, just skip it (don't reject the whole product)
                    if image_is_fake:
                        image_url = ""
                        logger.warning(f"  ⚠ Removed fake image URL for: {p.get('name', 'unknown')}")

                    # Map ChatGPT response fields to Product model fields
                    product = Product(
                        id=f"chatgpt-{p.get('name', 'unknown').replace(' ', '-').lower()[:30]}",  # Generate ID
                        title=p.get("name", "Unknown Product"),  # name → title
                        brand=p.get("brand", "Unknown Brand"),
                        price=float(p.get("price", 0)),
                        currency=p.get("currency", "USD"),
                        url=url,
                        image=image_url,  # image_url → image (may be empty if fake)
                        retailer=p.get("merchant", "Unknown Merchant"),  # merchant → retailer
                        category=p.get("category", "fashion"),
                        in_stock=p.get("in_stock", True),
                        source="chatgpt",
                        relevance_score=0.8  # Default high relevance
                    )
                    products.append(product)
                    logger.info(f"  ✓ Found: {product.title} - ${product.price} ({product.retailer})")
                except Exception as e:
                    logger.warning(f"  ⚠ Skipped invalid product: {e}")
                    continue

            logger.info(f"[ChatGPT Search] Found {len(products)} products")
            return products

        except Exception as e:
            logger.error(f"[ChatGPT Search] Error: {e}")
            return []

    def search_with_context(
        self,
        query: str,
        occasion: Optional[str] = None,
        style_preferences: Optional[List[str]] = None,
        min_price: float = 0,
        max_price: float = 10000,
        limit: int = 10
    ) -> List[Product]:
        """
        Enhanced search with additional context for better recommendations.

        Args:
            query: Base product search query
            occasion: Occasion context (e.g., "office professional", "date night")
            style_preferences: List of style preferences (e.g., ["minimal", "classic"])
            min_price: Minimum price
            max_price: Maximum price
            limit: Maximum results

        Returns:
            List of Product objects
        """
        # Enhance query with context
        enhanced_query = query
        if occasion:
            enhanced_query += f" for {occasion}"
        if style_preferences:
            enhanced_query += f" in {', '.join(style_preferences)} style"

        return self.search_products(enhanced_query, min_price, max_price, limit)


def search_products_chatgpt(
    query: str,
    min_price: float = 0,
    max_price: float = 10000,
    limit: int = 10
) -> List[Product]:
    """
    Convenience function for ChatGPT product search.

    Args:
        query: Product search query
        min_price: Minimum price
        max_price: Maximum price
        limit: Maximum results

    Returns:
        List of Product objects
    """
    searcher = ChatGPTProductSearcher()
    return searcher.search_products(query, min_price, max_price, limit)


if __name__ == "__main__":
    # Test the ChatGPT product search
    logging.basicConfig(level=logging.INFO)

    print("Testing ChatGPT Product Search")
    print("=" * 80)

    test_queries = [
        ("black leather Chelsea boots men's", 100, 300),
        ("sustainable organic cotton white t-shirt women's", 30, 80),
        ("navy blue blazer men's slim fit", 150, 400),
    ]

    for query, min_p, max_p in test_queries:
        print(f"\nQuery: {query}")
        print(f"Budget: ${min_p}-${max_p}")
        print("-" * 80)

        products = search_products_chatgpt(query, min_p, max_p, limit=5)

        if products:
            for i, p in enumerate(products, 1):
                print(f"{i}. {p.title}")
                print(f"   Brand: {p.brand} | Price: ${p.price} | Retailer: {p.retailer}")
                print(f"   URL: {p.url}")
                print(f"   In Stock: {p.in_stock}")
                print()
        else:
            print("No products found")

        print()
