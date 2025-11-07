#!/usr/bin/env python3
"""
Browser Pool Manager for Parallel Playwright Product Verification

Manages a pool of persistent browser instances with anti-detection features.
Implements hybrid architecture: 3 browsers × 5 contexts = 15 concurrent operations.

Key Features:
- Browser reuse to avoid 2-3s startup overhead
- Context pooling for lightweight concurrency
- Anti-detection: navigator.webdriver removal, property spoofing, UA randomization
- Connection lifecycle management with acquire/release pattern
"""

import asyncio
import random
from typing import Optional, List, Dict
from dataclasses import dataclass
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import logging

logger = logging.getLogger(__name__)


@dataclass
class BrowserConfig:
    """Configuration for anti-detection browser setup."""
    pool_size: int = 3  # Number of persistent browsers
    contexts_per_browser: int = 5  # Contexts per browser (15 total concurrent)
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    timeout: int = 60000  # 60s for sites with bot detection


# User agent pool for randomization
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class ContextPool:
    """Manages a pool of browser contexts for a single browser instance."""

    def __init__(self, browser: Browser, pool_size: int, config: BrowserConfig):
        self.browser = browser
        self.pool_size = pool_size
        self.config = config
        self._contexts: asyncio.Queue[BrowserContext] = asyncio.Queue(maxsize=pool_size)
        self._initialized = False

    async def initialize(self):
        """Create and configure all contexts in the pool."""
        if self._initialized:
            return

        logger.info(f"[ContextPool] Initializing {self.pool_size} contexts...")

        for i in range(self.pool_size):
            context = await self._create_context()
            await self._contexts.put(context)

        self._initialized = True
        logger.info(f"[ContextPool] Initialized {self.pool_size} contexts")

    async def _create_context(self) -> BrowserContext:
        """Create a new browser context with anti-detection features."""
        # Random user agent for diversity
        user_agent = random.choice(USER_AGENTS)

        context = await self.browser.new_context(
            viewport={'width': self.config.viewport_width, 'height': self.config.viewport_height},
            user_agent=user_agent,
            locale='en-US',
            timezone_id='America/New_York',
            # Anti-detection: Spoof permissions
            permissions=['geolocation', 'notifications'],
        )

        # Anti-detection: Remove navigator.webdriver flag and spoof properties
        await context.add_init_script("""
            // Remove webdriver flag
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Spoof navigator properties
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {
                        0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1,
                        name: "Chrome PDF Plugin"
                    },
                    {
                        0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format"},
                        description: "Portable Document Format",
                        filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                        length: 1,
                        name: "Chrome PDF Viewer"
                    }
                ]
            });

            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });

            // Spoof chrome object
            window.chrome = {
                runtime: {}
            };

            // Override permissions query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({state: Notification.permission}) :
                    originalQuery(parameters)
            );
        """)

        # Set default timeout
        context.set_default_timeout(self.config.timeout)

        return context

    async def acquire(self) -> BrowserContext:
        """Acquire a context from the pool (blocking if none available)."""
        if not self._initialized:
            await self.initialize()
        return await self._contexts.get()

    async def release(self, context: BrowserContext):
        """Release a context back to the pool."""
        # Clear cookies/storage for fresh state
        await context.clear_cookies()
        await self._contexts.put(context)

    async def close(self):
        """Close all contexts in the pool."""
        logger.info(f"[ContextPool] Closing {self.pool_size} contexts...")
        while not self._contexts.empty():
            context = await self._contexts.get()
            await context.close()
        logger.info(f"[ContextPool] Closed all contexts")


class BrowserPool:
    """
    Manages a pool of persistent browser instances with context pools.

    Architecture:
    - 3 browsers (persistent, reused across requests)
    - 5 contexts per browser (lightweight, cleared between uses)
    - Total: 15 concurrent operations

    Anti-detection:
    - Removes navigator.webdriver flag
    - Spoofs navigator properties (plugins, languages)
    - Randomizes user agents
    - Adds chrome object
    """

    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self._playwright = None
        self._browsers: List[Browser] = []
        self._context_pools: List[ContextPool] = []
        self._initialized = False
        self._round_robin_index = 0  # For load balancing
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Initialize the browser pool with all browsers and contexts."""
        if self._initialized:
            return

        logger.info(f"[BrowserPool] Initializing {self.config.pool_size} browsers...")

        self._playwright = await async_playwright().start()

        # Launch all browsers
        for i in range(self.config.pool_size):
            browser = await self._playwright.chromium.launch(
                headless=self.config.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',  # Anti-detection
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                ]
            )
            self._browsers.append(browser)

            # Create context pool for this browser
            pool = ContextPool(browser, self.config.contexts_per_browser, self.config)
            await pool.initialize()
            self._context_pools.append(pool)

            logger.info(f"[BrowserPool] Browser {i+1}/{self.config.pool_size} initialized with {self.config.contexts_per_browser} contexts")

        self._initialized = True
        logger.info(f"[BrowserPool] All {self.config.pool_size} browsers initialized ({self.config.pool_size * self.config.contexts_per_browser} total contexts)")

    async def acquire_context(self) -> tuple[BrowserContext, int]:
        """
        Acquire a context from any available browser (round-robin).

        Returns:
            tuple[BrowserContext, int]: (context, browser_index)
        """
        if not self._initialized:
            await self.initialize()

        # Round-robin load balancing across browsers
        async with self._lock:
            browser_index = self._round_robin_index
            self._round_robin_index = (self._round_robin_index + 1) % self.config.pool_size

        pool = self._context_pools[browser_index]
        context = await pool.acquire()

        return context, browser_index

    async def release_context(self, context: BrowserContext, browser_index: int):
        """Release a context back to its pool."""
        pool = self._context_pools[browser_index]
        await pool.release(context)

    async def close(self):
        """Close all browsers and contexts."""
        if not self._initialized:
            return

        logger.info("[BrowserPool] Closing all browsers and contexts...")

        # Close all context pools
        for pool in self._context_pools:
            await pool.close()

        # Close all browsers
        for browser in self._browsers:
            await browser.close()

        # Stop playwright
        if self._playwright:
            await self._playwright.stop()

        self._initialized = False
        logger.info("[BrowserPool] All browsers closed")

    async def __aenter__(self):
        """Context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()


# Global singleton instance
_browser_pool: Optional[BrowserPool] = None
_pool_lock = asyncio.Lock()


async def get_browser_pool(config: Optional[BrowserConfig] = None) -> BrowserPool:
    """
    Get or create the global browser pool singleton.

    This ensures only one pool exists across the entire application,
    preventing resource exhaustion from multiple pool instances.
    """
    global _browser_pool

    async with _pool_lock:
        if _browser_pool is None:
            _browser_pool = BrowserPool(config)
            await _browser_pool.initialize()
        return _browser_pool


async def close_browser_pool():
    """Close the global browser pool if it exists."""
    global _browser_pool

    async with _pool_lock:
        if _browser_pool is not None:
            await _browser_pool.close()
            _browser_pool = None
