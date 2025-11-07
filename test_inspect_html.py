"""
Inspect Google Shopping HTML structure to find correct selectors.
"""
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time


def inspect_html():
    """Inspect Google Shopping HTML"""

    driver = uc.Chrome(options=uc.ChromeOptions(), version_main=None)

    try:
        query = "black leather heels women"
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=shop&hl=en&gl=us"

        print(f"Loading: {url}")
        driver.get(url)
        time.sleep(5)

        html = driver.page_source

        # Save HTML to file for inspection
        with open("/tmp/google_shopping_html.html", "w") as f:
            f.write(html)

        print(f"HTML saved to /tmp/google_shopping_html.html ({len(html)} chars)")

        # Look for product links
        links = driver.find_elements(By.CSS_SELECTOR, "a")
        product_links = [link for link in links if 'shopping/product' in link.get_attribute('href') or '']

        print(f"\nFound {len(product_links)} product links")

        if product_links:
            print("\nFirst 3 product links:")
            for i, link in enumerate(product_links[:3]):
                print(f"\n  Link {i+1}:")
                print(f"    href: {link.get_attribute('href')}")
                print(f"    text: {link.text[:100] if link.text else 'No text'}")
                print(f"    parent tag: {link.find_element(By.XPATH, '..').tag_name}")

    finally:
        driver.quit()


if __name__ == "__main__":
    inspect_html()
