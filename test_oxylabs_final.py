"""Simple test to verify Oxylabs integration"""
import asyncio
import sys
sys.path.insert(0, '/Users/saksham/Codes/Elara-Joining')

from integrations.oxylabs_client import OxylabsClient

async def test():
    client = OxylabsClient()
    print("=" * 80)
    print("OXYLABS INTEGRATION TEST")
    print("=" * 80)

    # Test search
    products = await client.search_products(
        descriptor="white sneakers",
        price_max=200,
        max_results=3
    )

    print(f"\n✓ SUCCESS: Found {len(products)} products from Oxylabs")

    if products:
        print("\nSample product:")
        p = products[0]
        print(f"  ID: {p.id}")
        print(f"  Title: {p.title}")
        print(f"  Price: ${p.price}")
        print(f"  Retailer: {p.retailer}")
        print(f"  URL: {p.url[:100]}...")
        print(f"  Source: {p.source}")

    return len(products) > 0

if __name__ == "__main__":
    success = asyncio.run(test())
    if success:
        print("\n✓ OXYLABS INTEGRATION: WORKING")
        exit(0)
    else:
        print("\n✗ OXYLABS INTEGRATION: FAILED")
        exit(1)
