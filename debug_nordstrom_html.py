"""
Debug script - see what HTML we're getting from Nordstrom
"""
import asyncio
import logging
from integrations.playwright_mcp_client import PlaywrightMCPClient

logging.basicConfig(level=logging.INFO)

async def debug_nordstrom_page():
    """See what HTML we get from Nordstrom browse page"""

    url = "https://www.nordstrom.com/browse/women/clothing/coats-jackets?filterByColor=black"

    print(f"Navigating to: {url}")
    print()

    client = PlaywrightMCPClient()

    try:
        # Navigate
        await client.navigate(url, timeout=15000)

        # Wait a bit for JS to load
        print("Waiting 5 seconds for JavaScript to render...")
        await asyncio.sleep(5)

        # Get HTML
        html = await client.get_visible_html(remove_scripts=True, max_length=100000)

        print(f"HTML length: {len(html)} characters")
        print()

        # Save to file for inspection
        with open("/tmp/nordstrom_page.html", "w") as f:
            f.write(html)

        print("Full HTML saved to: /tmp/nordstrom_page.html")
        print()

        # Show a snippet
        print("HTML snippet (first 2000 chars):")
        print("=" * 70)
        print(html[:2000])
        print("=" * 70)

        # Look for links
        import re
        href_pattern = r'href=["\']([^"\']+)["\']'
        all_links = re.findall(href_pattern, html)
        print(f"\nFound {len(all_links)} href attributes")

        # Show some sample links
        if all_links:
            print("\nFirst 10 links:")
            for link in all_links[:10]:
                print(f"  - {link}")

        await client.close()

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_nordstrom_page())
