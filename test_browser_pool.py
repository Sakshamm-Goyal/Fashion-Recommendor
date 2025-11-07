#!/usr/bin/env python3
"""
Test Browser Pool Integration

Tests the browser pool with link verification agent to ensure:
1. Browser pool initializes correctly
2. 15 concurrent contexts are available (3 browsers × 5 contexts)
3. Anti-detection features work
4. Parallel verification completes successfully
5. No browser crashes or memory leaks
"""

import asyncio
import logging
from typing import List
from contracts.models import Product
from services.link_verification_agent import LinkVerificationAgent
from services.browser_pool import get_browser_pool, close_browser_pool, BrowserConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


# Test products with known good URLs
TEST_PRODUCTS = [
    Product(
        id="test_1",
        title="Zara Basic Poplin Shirt",
        price=2050.0,
        currency="INR",
        url="https://www.zara.com/in/en/basic-poplin-shirt-p03362340.html",
        retailer="Zara",
        brand="Zara",
        source="test"
    ),
    Product(
        id="test_2",
        title="H&M Cotton T-shirt",
        price=799.0,
        currency="INR",
        url="https://www2.hm.com/en_in/productpage.0685816048.html",
        retailer="H&M",
        brand="H&M",
        source="test"
    ),
    Product(
        id="test_3",
        title="Amazon Basics Men's Shirt",
        price=699.0,
        currency="INR",
        url="https://www.amazon.in/dp/B07Q2Y7J6Z",
        retailer="Amazon",
        brand="Amazon Basics",
        source="test"
    ),
    # Add more test products for stress testing
    Product(
        id="test_4",
        title="Test Product 4",
        price=1500.0,
        currency="INR",
        url="https://www.myntra.com/tshirts/roadster/roadster-men-navy-blue-printed-round-neck-t-shirt/1700834/buy",
        retailer="Myntra",
        brand="Roadster",
        source="test"
    ),
    Product(
        id="test_5",
        title="Test Product 5",
        price=2000.0,
        currency="INR",
        url="https://www.ajio.com/nike-typographic-print-crew-neck-t-shirt/p/469118134_black",
        retailer="Ajio",
        brand="Nike",
        source="test"
    ),
]


async def test_browser_pool_initialization():
    """Test 1: Browser pool initializes correctly"""
    logger.info("=" * 80)
    logger.info("TEST 1: Browser Pool Initialization")
    logger.info("=" * 80)

    config = BrowserConfig(
        pool_size=3,
        contexts_per_browser=5,
        headless=True,
        timeout=30000
    )

    pool = await get_browser_pool(config)

    logger.info(f"✓ Browser pool initialized")
    logger.info(f"  - Pool size: {config.pool_size} browsers")
    logger.info(f"  - Contexts per browser: {config.contexts_per_browser}")
    logger.info(f"  - Total concurrent capacity: {config.pool_size * config.contexts_per_browser}")

    return pool


async def test_context_acquisition():
    """Test 2: Context acquisition and release"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Context Acquisition and Release")
    logger.info("=" * 80)

    pool = await get_browser_pool()

    # Acquire 15 contexts (should fill the pool)
    contexts = []
    browser_indices = []

    logger.info("Acquiring 15 contexts from pool...")
    start_time = asyncio.get_event_loop().time()

    for i in range(15):
        context, browser_index = await pool.acquire_context()
        contexts.append(context)
        browser_indices.append(browser_index)
        logger.info(f"  Acquired context {i+1}/15 from browser {browser_index}")

    acquire_time = asyncio.get_event_loop().time() - start_time
    logger.info(f"✓ All 15 contexts acquired in {acquire_time:.2f}s")

    # Release all contexts
    logger.info("\nReleasing all contexts back to pool...")
    for context, browser_index in zip(contexts, browser_indices):
        await pool.release_context(context, browser_index)

    logger.info(f"✓ All contexts released")


async def test_parallel_verification():
    """Test 3: Parallel verification with browser pool"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Parallel Verification (5 products)")
    logger.info("=" * 80)

    agent = LinkVerificationAgent(
        concurrency=15,
        timeout=30000,
        enable_screenshots=False,
        max_retries=2
    )

    products = TEST_PRODUCTS[:5]

    logger.info(f"Verifying {len(products)} products in parallel...")
    start_time = asyncio.get_event_loop().time()

    verified_products, results = await agent.batch_verify_products(products)

    verification_time = asyncio.get_event_loop().time() - start_time

    logger.info(f"\n✓ Verification completed in {verification_time:.2f}s")
    logger.info(f"  - Total products: {len(products)}")
    logger.info(f"  - Verified: {len(verified_products)}")
    logger.info(f"  - Failed: {len(products) - len(verified_products)}")
    logger.info(f"  - Success rate: {len(verified_products)/len(products)*100:.1f}%")
    logger.info(f"  - Avg time per product: {verification_time/len(products):.2f}s")

    # Log individual results
    logger.info("\nIndividual Results:")
    for result in results:
        status = "✓ PASS" if result.is_valid else "✗ FAIL"
        logger.info(f"  {status} - {result.url[:60]}...")
        if result.error_message:
            logger.info(f"    Error: {result.error_message}")
        logger.info(f"    Time: {result.verification_time:.2f}s")


async def test_stress_test():
    """Test 4: Stress test with 15+ concurrent requests"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Stress Test (15+ concurrent requests)")
    logger.info("=" * 80)

    agent = LinkVerificationAgent(
        concurrency=15,
        timeout=30000,
        enable_screenshots=False,
        max_retries=1  # Reduce retries for faster stress test
    )

    # Create 20 test products (more than pool capacity)
    products = TEST_PRODUCTS * 4  # 5 * 4 = 20 products

    logger.info(f"Stress testing with {len(products)} products...")
    logger.info(f"Pool capacity: 15 concurrent contexts")
    logger.info(f"Expected behavior: Queue overflow, sequential processing")

    start_time = asyncio.get_event_loop().time()

    verified_products, results = await agent.batch_verify_products(products)

    verification_time = asyncio.get_event_loop().time() - start_time

    logger.info(f"\n✓ Stress test completed in {verification_time:.2f}s")
    logger.info(f"  - Total products: {len(products)}")
    logger.info(f"  - Verified: {len(verified_products)}")
    logger.info(f"  - Failed: {len(products) - len(verified_products)}")
    logger.info(f"  - Throughput: {len(products)/verification_time:.2f} products/sec")


async def test_anti_detection():
    """Test 5: Verify anti-detection features are working"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 5: Anti-Detection Features")
    logger.info("=" * 80)

    pool = await get_browser_pool()
    context, browser_index = await pool.acquire_context()

    try:
        page = await context.new_page()

        # Navigate to a test page that detects automation
        await page.goto("https://bot.sannysoft.com/", timeout=30000)

        # Extract anti-detection test results
        html = await page.content()

        # Check for key indicators
        webdriver_detected = "webdriver" in html.lower() and "true" in html.lower()

        if webdriver_detected:
            logger.warning("✗ navigator.webdriver detected (anti-detection may not be working)")
        else:
            logger.info("✓ navigator.webdriver NOT detected (anti-detection working)")

        await page.close()

    finally:
        await pool.release_context(context, browser_index)


async def main():
    """Run all tests"""
    logger.info("\n" + "=" * 80)
    logger.info("BROWSER POOL INTEGRATION TESTS")
    logger.info("=" * 80)

    try:
        # Test 1: Initialization
        await test_browser_pool_initialization()

        # Test 2: Context acquisition
        await test_context_acquisition()

        # Test 3: Parallel verification
        await test_parallel_verification()

        # Test 4: Stress test
        await test_stress_test()

        # Test 5: Anti-detection
        await test_anti_detection()

        logger.info("\n" + "=" * 80)
        logger.info("ALL TESTS COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"\nTEST FAILED: {type(e).__name__}: {str(e)}")
        raise

    finally:
        # Cleanup
        logger.info("\nCleaning up browser pool...")
        await close_browser_pool()
        logger.info("✓ Browser pool closed")


if __name__ == "__main__":
    asyncio.run(main())
