"""
Test Google Shopping scraper to debug selector issues.
"""
import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time


def test_google_shopping():
    """Test Google Shopping page structure"""

    # Create Chrome driver
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(10)

    try:
        # Build Google Shopping URL
        query = "black leather heels women"
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=shop&hl=en&gl=us"

        print(f"[Test] Loading: {url}")
        driver.get(url)

        # Wait for page to load
        time.sleep(3)

        # Save screenshot
        driver.save_screenshot("/tmp/google_shopping_test.png")
        print("[Test] Screenshot saved to /tmp/google_shopping_test.png")

        # Get page source
        html = driver.page_source
        print(f"\n[Test] Page source length: {len(html)} characters")

        # Try different selectors
        selectors_to_try = [
            'div[data-docid]',
            'div[data-sh-pd]',
            'div[data-product-id]',
            '.sh-dgr__content',
            '.sh-dgr__grid-result',
            '[data-hveid]',
            'a[href*="/shopping/product/"]'
        ]

        print("\n[Test] Trying different selectors:")
        for selector in selectors_to_try:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"  • {selector}: Found {len(elements)} elements")
                if elements and len(elements) > 0:
                    # Print first element HTML
                    print(f"    First element HTML (truncated): {elements[0].get_attribute('outerHTML')[:200]}")
            except Exception as e:
                print(f"  • {selector}: Error - {e}")

        # Check if we're blocked
        if 'unusual traffic' in html.lower() or 'captcha' in html.lower():
            print("\n⚠️  [Test] Google is blocking us with CAPTCHA!")

        # Check for product grid
        if 'shopping' in html.lower():
            print("\n✓ [Test] Page contains 'shopping' keyword")
        else:
            print("\n✗ [Test] Page does not contain 'shopping' keyword")

    finally:
        driver.quit()


if __name__ == "__main__":
    test_google_shopping()
