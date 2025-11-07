"""
Test OpenSERP integration in product search service.
"""
import asyncio
import sys
from services.product_search_service import HybridProductSearch


async def test_openserp_integration():
    """Test that OpenSERP is working as primary search source"""
    print("\n" + "="*80)
    print("Testing OpenSERP Integration")
    print("="*80 + "\n")

    # Initialize search service
    print("[1/3] Initializing product search service...")
    search_service = HybridProductSearch()

    # Temporarily disable visual scraping to test OpenSERP only
    search_service.enable_visual_scraping = False

    # Test search queries
    test_queries = [
        ("black leather heels women", 150.0),
        ("Zara black tshirt size L", 100.0),
        ("Nike white sneakers", 200.0),
    ]

    for i, (query, max_price) in enumerate(test_queries, 1):
        print(f"\n[{i+1}/3] Testing query: '{query}' (max_price: ${max_price})")
        print("-" * 80)

        # Search for products
        products = await search_service.search_multi_source(
            descriptor=query,
            budget={"soft_cap": max_price * 0.8, "hard_cap": max_price},
            filters={"gender": "women"},
            k=10
        )

        print(f"\n✓ Found {len(products)} products\n")

        if products:
            # Show first 3 products
            for j, product in enumerate(products[:3], 1):
                print(f"{j}. {product.title[:80]}")
                print(f"   URL: {product.url[:100]}...")
                print(f"   Source: {product.source if hasattr(product, 'source') else 'unknown'}")
                print(f"   Relevance: {product.relevance_score:.2f}")
                if product.price:
                    print(f"   Price: ${product.price:.2f}")
                print()
        else:
            print("❌ No products found - OpenSERP may not be working\n")

    print("="*80)
    print("Test Complete!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_openserp_integration())
