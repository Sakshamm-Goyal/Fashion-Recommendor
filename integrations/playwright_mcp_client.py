"""
Playwright MCP Client for Elara

This module provides a Python client for interacting with Playwright MCP tools.
It wraps the MCP Playwright functions to provide a clean async interface.

The actual Playwright operations are performed by invoking Claude Code's MCP tools.
Since this is Python code that will be executed by the user's application, we need
to provide a way to call the MCP tools from within the Python runtime.

NOTE: This implementation requires the Playwright MCP tools to be callable from
the Python environment. In production, you would either:
1. Use a REST/RPC bridge to communicate with the MCP server
2. Integrate directly with Playwright Python library
3. Use subprocess to invoke Claude Code CLI with tool calls

For now, we'll implement using Playwright Python library as a fallback.

Author: Elara Team
"""

import logging
from typing import Optional, Dict, Any
import asyncio

logger = logging.getLogger(__name__)


class PlaywrightMCPClient:
    """
    Client for Playwright MCP operations.

    This class provides browser automation using Playwright.
    It attempts to use the real Playwright library if available.
    """

    def __init__(self):
        """Initialize Playwright MCP client"""
        self.current_url = None
        self._browser_active = False
        self._browser = None
        self._page = None
        self._playwright = None

    async def _ensure_browser(self):
        """Ensure browser is initialized"""
        if self._browser_active and self._page:
            return

        try:
            from playwright.async_api import async_playwright

            logger.info("[PlaywrightMCP] Initializing Playwright browser")
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._page = await self._browser.new_page()
            self._browser_active = True
            logger.info("[PlaywrightMCP] Browser initialized successfully")

        except ImportError:
            logger.error("[PlaywrightMCP] Playwright library not available. Install with: pip install playwright && playwright install")
            raise RuntimeError("Playwright library not installed")
        except Exception as e:
            logger.error(f"[PlaywrightMCP] Failed to initialize browser: {e}")
            raise

    async def navigate(
        self,
        url: str,
        timeout: int = 10000,
        browser_type: str = "chromium",
        headless: bool = True
    ) -> Dict[str, Any]:
        """
        Navigate to a URL.

        Args:
            url: URL to navigate to
            timeout: Navigation timeout in milliseconds
            browser_type: Browser to use (chromium, firefox, webkit)
            headless: Run in headless mode

        Returns:
            Navigation result
        """
        logger.info(f"[PlaywrightMCP] Navigating to: {url}")

        try:
            await self._ensure_browser()
            await self._page.goto(url, timeout=timeout, wait_until="networkidle")
            self.current_url = url

            return {
                "status": "success",
                "url": url,
                "message": "Navigation successful"
            }
        except Exception as e:
            logger.error(f"[PlaywrightMCP] Navigation failed: {e}")
            return {
                "status": "error",
                "url": url,
                "message": str(e)
            }

    async def get_visible_html(
        self,
        selector: Optional[str] = None,
        clean_html: bool = True,
        remove_scripts: bool = True,
        max_length: int = 50000
    ) -> str:
        """
        Get HTML content of current page.

        Args:
            selector: Optional CSS selector to limit HTML
            clean_html: Remove unnecessary tags
            remove_scripts: Remove script tags
            max_length: Maximum length of returned HTML

        Returns:
            HTML content as string
        """
        logger.info(f"[PlaywrightMCP] Getting HTML from: {self.current_url}")

        try:
            if not self._page:
                return "<html><!-- Browser not initialized --></html>"

            if selector:
                element = await self._page.query_selector(selector)
                if element:
                    html = await element.inner_html()
                else:
                    html = ""
            else:
                html = await self._page.content()

            # Apply transformations
            if remove_scripts:
                # Simple script tag removal
                import re
                html = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html, flags=re.IGNORECASE)

            # Truncate if needed
            if len(html) > max_length:
                html = html[:max_length]

            return html

        except Exception as e:
            logger.error(f"[PlaywrightMCP] Failed to get HTML: {e}")
            return f"<html><!-- Error: {e} --></html>"

    async def screenshot(
        self,
        name: str,
        full_page: bool = False,
        selector: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Take a screenshot of current page.

        Args:
            name: Name for screenshot
            full_page: Capture full page
            selector: Optional element selector

        Returns:
            Screenshot result
        """
        logger.info(f"[PlaywrightMCP] Taking screenshot: {name}")

        try:
            if not self._page:
                return {"status": "error", "message": "Browser not initialized"}

            path = f"/tmp/{name}.png"

            if selector:
                element = await self._page.query_selector(selector)
                if element:
                    await element.screenshot(path=path)
            else:
                await self._page.screenshot(path=path, full_page=full_page)

            return {
                "status": "success",
                "name": name,
                "path": path,
                "message": "Screenshot captured"
            }
        except Exception as e:
            logger.error(f"[PlaywrightMCP] Screenshot failed: {e}")
            return {"status": "error", "message": str(e)}

    async def click(self, selector: str) -> Dict[str, Any]:
        """Click an element"""
        logger.info(f"[PlaywrightMCP] Clicking: {selector}")

        try:
            if not self._page:
                return {"status": "error", "message": "Browser not initialized"}

            await self._page.click(selector)
            return {"status": "success"}
        except Exception as e:
            logger.error(f"[PlaywrightMCP] Click failed: {e}")
            return {"status": "error", "message": str(e)}

    async def fill(self, selector: str, value: str) -> Dict[str, Any]:
        """Fill an input field"""
        logger.info(f"[PlaywrightMCP] Filling {selector} with: {value}")

        try:
            if not self._page:
                return {"status": "error", "message": "Browser not initialized"}

            await self._page.fill(selector, value)
            return {"status": "success"}
        except Exception as e:
            logger.error(f"[PlaywrightMCP] Fill failed: {e}")
            return {"status": "error", "message": str(e)}

    async def evaluate(self, script: str) -> Any:
        """Execute JavaScript in browser"""
        logger.info(f"[PlaywrightMCP] Evaluating JS: {script[:100]}...")

        try:
            if not self._page:
                return None

            result = await self._page.evaluate(script)
            return result
        except Exception as e:
            logger.error(f"[PlaywrightMCP] Evaluate failed: {e}")
            return None

    async def close(self) -> Dict[str, Any]:
        """Close browser"""
        logger.info("[PlaywrightMCP] Closing browser")

        try:
            if self._page:
                await self._page.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()

            self._page = None
            self._browser = None
            self._playwright = None
            self._browser_active = False

            return {"status": "success"}
        except Exception as e:
            logger.error(f"[PlaywrightMCP] Close failed: {e}")
            return {"status": "error", "message": str(e)}

    @property
    def is_active(self) -> bool:
        """Check if browser is active"""
        return self._browser_active
