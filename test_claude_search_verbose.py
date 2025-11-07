#!/usr/bin/env python3
"""Quick test of Claude Web Search with verbose logging"""

import asyncio
import logging
from integrations.claude_web_search import ClaudeWebSearchClient

# Enable all logging
logging.basicConfig(level=logging.DEBUG)

async def test_search():
    client = ClaudeWebSearchClient()

    print("="*80)
    print("Searching for: black heels women")
    print("="*80)

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
