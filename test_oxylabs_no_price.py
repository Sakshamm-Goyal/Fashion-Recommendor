"""Test Oxylabs without price filter"""
import asyncio
import sys
sys.path.insert(0, '/Users/saksham/Codes/Elara-Joining')

from integrations.oxylabs_client import OxylabsClient

async def test():
    client = OxylabsClient()
    print("Testing Oxylabs WITHOUT price filter...")
    print()

    # Test without price constraint
    products = await client.search_products(
        descriptor="white sneakers",
        price_max=None,  # No price filter
        max_results=5
    )

    print(f"\nFound {len(products)} products")
    for i, product in enumerate(products, 1):
        print(f"\n{i}. {product.name}")
        print(f"   Price: ${product.price}")
        print(f"   Retailer: {product.retailer}")
        print(f"   Link: {product.buy_link[:80]}...")

if __name__ == "__main__":
    asyncio.run(test())
