#!/usr/bin/env python3
"""Quick test of Claude Web Search"""

import asyncio
from integrations.claude_web_search import ClaudeWebSearchClient

async def test_search():
    client = ClaudeWebSearchClient()

    print("Searching for: black heels")
    products = await client.search_products(
        query="black heels women",
        max_results=5,
        max_price=150
    )

    print(f"\nFound {len(products)} products:")
    for p in products[:3]:
        print(f"  • {p.title}")
        print(f"    Price: {p.currency} {p.price}")
        print(f"    URL: {p.url}")
        print(f"    Retailer: {p.retailer}")
        print()

if __name__ == "__main__":
    asyncio.run(test_search())
