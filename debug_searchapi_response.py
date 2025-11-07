#!/usr/bin/env python3
"""
Debug script to inspect SearchAPI response structure
"""

import asyncio
import json
from integrations.searchapi_client import SearchAPIClient
import config


async def main():
    """Fetch and inspect SearchAPI raw response"""
    client = SearchAPIClient(
        api_key=config.SEARCHAPI_KEY,
        default_gl="us",
        default_hl="en"
    )

    try:
        # Search for a simple product
        print("Fetching SearchAPI response for 'black heels'...\n")
        data = await client.search_shopping(
            query="black heels",
            price_max=200,
            page=1
        )

        # Print full response structure
        print("="*70)
        print("FULL RESPONSE STRUCTURE:")
        print("="*70)
        print(json.dumps(data, indent=2)[:3000])  # First 3000 chars
        print("\n...(truncated)\n")

        # Print first shopping result in detail
        if "shopping_results" in data and len(data["shopping_results"]) > 0:
            print("="*70)
            print("FIRST SHOPPING RESULT - DETAILED:")
            print("="*70)
            first_item = data["shopping_results"][0]
            print(json.dumps(first_item, indent=2))

            print("\n" + "="*70)
            print("AVAILABLE URL FIELDS:")
            print("="*70)
            for key, value in first_item.items():
                if "link" in key.lower() or "url" in key.lower():
                    print(f"  {key}: {value}")

        await client.close()

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
