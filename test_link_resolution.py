"""
Test script for link resolution with real Playwright
"""
import asyncio
import logging
from services.link_resolver import LinkResolver
from contracts.models import Product

# Set up logging
logging.basicConfig(level=logging.INFO)

async def test_link_resolution():
    """Test resolving a single OpenSERP browse page"""

    print("=" * 70)
    print("Testing Link Resolution with Real Playwright")
    print("=" * 70)
    print()

    # Create a test product with a browse page URL
    test_product = Product(
        id="test_001",
        title="Women's Black Leather Jackets - Nordstrom",
        price=None,
        currency="USD",
        url="https://www.nordstrom.com/browse/women/clothing/coats-jackets?filterByColor=black",
        image=None,
        retailer="Nordstrom",
        brand=None,
        description="Browse page for black leather jackets",
        source="openserp"
    )

    print(f"Test URL: {test_product.url}")
    print()

    # Initialize link resolver
    resolver = LinkResolver(
        max_products_per_page=5,
        timeout=15000,  # 15 seconds
        concurrency=1  # Just one for testing
    )

    print("Initializing browser and resolving links...")
    print()

    try:
        # Resolve the link
        resolved_products = await resolver.resolve_products(
            products=[test_product],
            query_hints={"test_001": "black leather jacket women"}
        )

        print("=" * 70)
        print(f"Results: Found {len(resolved_products)} product links")
        print("=" * 70)
        print()

        if resolved_products:
            for i, product in enumerate(resolved_products[:10], 1):
                print(f"{i}. {product.title}")
                print(f"   URL: {product.url}")
                print(f"   Retailer: {product.retailer}")
                print(f"   Source: {product.source}")
                print()
        else:
            print("No products found. This could mean:")
            print("  - The page structure has changed")
            print("  - Product selectors need updating")
            print("  - The page requires JavaScript to load products")
            print()

        print("=" * 70)
        print("Test Complete")
        print("=" * 70)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_link_resolution())
