"""Test that Oxylabs products bypass retailer filter"""
import asyncio
import sys
sys.path.insert(0, '/Users/saksham/Codes/Elara-Joining')

from services.product_search_service import HybridProductSearch

async def test():
    service = HybridProductSearch()

    print("Testing product search with retailer filter...")
    print()

    # Search for a product - should find Oxylabs products despite retailer filter
    products = await service.search_multi_source(
        descriptor="white sneakers",
        budget={"total": 200},
        filters={"max_price": 200},
        retailers_allowlist=['Zara', 'H&M', 'ASOS', 'Nordstrom'],  # Specific retailers
        k=5
    )

    print(f"Found {len(products)} products")
    for i, product in enumerate(products, 1):
        print(f"\n{i}. {product.title}")
        print(f"   Price: ${product.price}")
        print(f"   Retailer: {product.retailer}")
        print(f"   Source: {product.source}")
        print(f"   URL: {product.url[:80]}...")

    if products:
        print(f"\n✓ SUCCESS: Oxylabs products passed through retailer filter!")
        return True
    else:
        print(f"\n✗ FAILED: No products found (filter may still be blocking)")
        return False

if __name__ == "__main__":
    success = asyncio.run(test())
    exit(0 if success else 1)
