#!/usr/bin/env python3
import asyncio
from integrations.searchapi_client import SearchAPIClient
import config

async def test():
    client = SearchAPIClient(
        api_key=config.SEARCHAPI_KEY,
        base_url=config.SEARCHAPI_BASE_URL
    )
    try:
        result = await client.search_products(
            descriptor='Black patent leather pumps',
            price_max=300.0,
            max_results=10,
            prefer_new=True
        )
        print(f'Success! Found {len(result)} products')
        if result:
            print(f'First product: {result[0].title} - ${result[0].price}')
    except Exception as e:
        print(f'Error: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == '__main__':
    asyncio.run(test())
