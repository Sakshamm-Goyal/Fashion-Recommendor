"""
Test undetected-chromedriver to bypass Google's bot detection.
"""
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time


def test_undetected_chrome():
    """Test with undetected-chromedriver"""

    print("[Test] Creating undetected Chrome driver...")
    options = uc.ChromeOptions()
    # DON'T use headless for testing - Google blocks headless more aggressively
    # options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = uc.Chrome(options=options, version_main=None)

    try:
        # Build Google Shopping URL
        query = "black leather heels women"
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=shop&hl=en&gl=us"

        print(f"[Test] Loading: {url}")
        driver.get(url)

        # Wait longer for page to load
        print("[Test] Waiting 5 seconds for page to load...")
        time.sleep(5)

        # Save screenshot
        driver.save_screenshot("/tmp/google_shopping_undetected.png")
        print("[Test] Screenshot saved to /tmp/google_shopping_undetected.png")

        # Get page source
        html = driver.page_source
        print(f"\n[Test] Page source length: {len(html)} characters")

        # Check for CAPTCHA
        if 'unusual traffic' in html.lower() or 'captcha' in html.lower():
            print("\n⚠️  [Test] Still getting CAPTCHA!")
        else:
            print("\n✓ [Test] No CAPTCHA detected!")

        # Check for shopping content
        if 'shopping' in html.lower():
            print("✓ [Test] Page contains 'shopping' keyword")

        # Try different selectors
        selectors_to_try = [
            'div[data-docid]',
            'div[data-sh-pd]',
            '[data-hveid]',
            'a[href*="/shopping/product/"]',
            'div.sh-dgr__gr-auto',
            'div[jscontroller]',
            'div[data-aid]'
        ]

        print("\n[Test] Trying different selectors:")
        for selector in selectors_to_try:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"  • {selector}: Found {len(elements)} elements")
                if elements and len(elements) > 0:
                    # Print first element info
                    first = elements[0]
                    print(f"    Text: {first.text[:100] if first.text else 'No text'}")
            except Exception as e:
                print(f"  • {selector}: Error - {e}")

        print("\n[Test] Keeping browser open for 10 seconds for manual inspection...")
        time.sleep(10)

    finally:
        driver.quit()


if __name__ == "__main__":
    test_undetected_chrome()
