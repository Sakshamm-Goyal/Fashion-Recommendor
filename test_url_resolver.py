#!/usr/bin/env python3
"""
Test URL resolver with a real Google Shopping URL
"""

import asyncio
from services.url_resolver import URLResolver


async def main():
    """Test URL resolution"""
    resolver = URLResolver(concurrency=2, timeout=10000)

    # Real Google Shopping URL from our debug output
    test_url = "https://www.google.com/search?q=black+heels+under+200&oq=black+heels+under+200&gl=us&hl=en&udm=28&shoprs=CAESDRILEQAAAACE16dBGAEYFioLYmxhY2sgaGVlbHMyIwgFEgpVbmRlciAkMjAwGAIiDRILEQAAAACE16dBGAEqAhgBWImqIGAC&start=0#oshopproduct=gid:16547879849347082449,mid:576462901044871590,oid:18202034215650206539,iid:13084882809453193228,rds:UENfMTY1NDc4Nzk4NDkzNDcwODI0NDl8UFJPRF9QQ18xNjU0Nzg3OTg0OTM0NzA4MjQ0OQ==,pvt:hg,pvo:3&oshop=apv&pvs=0"

    print("Testing URL Resolver")
    print("="*70)
    print(f"\nOriginal URL: {test_url[:100]}...")
    print(f"\nIs Google Shopping URL: {resolver.is_google_shopping_url(test_url)}")
    print(f"Needs resolution: {resolver.needs_resolution(test_url)}")

    print("\nResolving URL...")
    resolved = await resolver.resolve_url(test_url)

    print(f"\nResolved URL: {resolved}")
    print(f"Is still Google Shopping: {resolver.is_google_shopping_url(resolved)}")

    if resolved != test_url and not resolver.is_google_shopping_url(resolved):
        print("\n✓ SUCCESS: URL was resolved to a product page!")
    else:
        print("\n⚠ NOTICE: URL could not be fully resolved (this is OK for some URLs)")


if __name__ == "__main__":
    asyncio.run(main())
