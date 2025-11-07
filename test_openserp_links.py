#!/usr/bin/env python3
"""
Quick test to verify OpenSERP is returning working product links.
"""
import asyncio
import sys
from services.product_search_service import search_products_hybrid

async def test_openserp_links():
    """Test OpenSERP product search and link validity."""
    print("=" * 80)
    print("Testing OpenSERP Product Search")
    print("=" * 80)

    # Test search for a simple product
    query = "black leather jacket women"
    budget = {"soft_cap": 150.0, "hard_cap": 200.0}

    print(f"\nSearching for: {query}")
    print(f"Budget: ${budget['soft_cap']}-${budget['hard_cap']}")
    print("-" * 80)

    try:
        products = await search_products_hybrid(
            descriptor=query,
            budget=budget,
            retailers_allowlist=None
        )

        print(f"\n✓ Found {len(products)} products")

        if products:
            print("\nFirst 3 products:")
            print("-" * 80)
            for i, product in enumerate(products[:3], 1):
                print(f"\n{i}. {product.title}")
                print(f"   Retailer: {product.retailer}")
                print(f"   Price: ${product.price} {product.currency}" if product.price else "   Price: Not available")
                print(f"   Link: {product.url}")

                # Check if link looks valid (not obviously fake)
                if product.url and product.url.startswith("http"):
                    print(f"   ✓ Link format looks valid")
                else:
                    print(f"   ✗ Link format suspicious: {product.url}")

            print("\n" + "=" * 80)
            print("TEST COMPLETE - Please manually verify a few links in browser")
            print("=" * 80)
            return 0
        else:
            print("\n✗ No products found - OpenSERP may not be working")
            return 1

    except Exception as e:
        print(f"\n✗ Error during search: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(test_openserp_links()))
