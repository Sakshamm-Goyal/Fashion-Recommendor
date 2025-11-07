"""
Retailer-Specific Patterns for Link Verification Agent

This module provides intelligent selector patterns for major fashion retailers
to verify product availability, pricing, and add-to-cart functionality.

Features:
- Pre-configured patterns for 20+ major retailers
- Universal fallback patterns for unknown retailers
- Smart selector detection with multiple alternatives
- Out-of-stock detection patterns
- Price extraction patterns

Author: Elara Team
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import re


@dataclass
class RetailerPattern:
    """Pattern configuration for a specific retailer"""
    name: str
    domain_patterns: List[str]  # URL patterns to match (e.g., "nordstrom.com")
    add_to_cart_selectors: List[str]  # CSS selectors for Add to Cart button
    price_selectors: List[str]  # CSS selectors for price display
    out_of_stock_patterns: List[str]  # Text patterns indicating out of stock
    product_title_selectors: List[str]  # CSS selectors for product title
    size_selectors: Optional[List[str]] = None  # CSS selectors for size dropdown
    color_selectors: Optional[List[str]] = None  # CSS selectors for color selector


# Major Fashion Retailers - Pre-configured Patterns
RETAILER_PATTERNS = {
    "nordstrom": RetailerPattern(
        name="Nordstrom",
        domain_patterns=["nordstrom.com", "nordstromrack.com"],
        add_to_cart_selectors=[
            "[data-test-id='add-to-bag']",
            "button[id*='addToBag']",
            "button:has-text('Add to Bag')",
            "[aria-label*='Add to Bag']"
        ],
        price_selectors=[
            "[data-test='product-price']",
            "[class*='price'] span",
            ".product-price",
            "[aria-label*='Price']"
        ],
        out_of_stock_patterns=[
            "out of stock",
            "sold out",
            "not available",
            "currently unavailable",
            "notify me when available"
        ],
        product_title_selectors=[
            "h1[data-test='product-title']",
            "h1.product-title",
            "h1[id*='title']"
        ],
        size_selectors=["[data-test='size-selector']", "select[name='size']"],
        color_selectors=["[data-test='color-selector']", "[class*='color-swatch']"]
    ),

    "macys": RetailerPattern(
        name="Macy's",
        domain_patterns=["macys.com"],
        add_to_cart_selectors=[
            "#addToBagButton",
            "button[data-auto='add-to-bag']",
            "button:has-text('Add to Bag')",
            "[id*='addToBag']"
        ],
        price_selectors=[
            "[data-auto='product-price']",
            ".price",
            "[class*='product-price']",
            "span[class*='price']"
        ],
        out_of_stock_patterns=[
            "out of stock",
            "sold out",
            "unavailable",
            "not available online"
        ],
        product_title_selectors=[
            "h1[data-auto='product-title']",
            "h1.product-title"
        ]
    ),

    "asos": RetailerPattern(
        name="ASOS",
        domain_patterns=["asos.com"],
        add_to_cart_selectors=[
            "[data-test-id='add-button']",
            "button[data-auto-id='add-to-bag']",
            "button:has-text('Add to bag')",
            "[class*='add-button']"
        ],
        price_selectors=[
            "[data-testid='current-price']",
            "[class*='product-price']",
            "span[data-id='current-price']"
        ],
        out_of_stock_patterns=[
            "out of stock",
            "sold out",
            "not available"
        ],
        product_title_selectors=[
            "h1[class*='product-title']",
            "h1"
        ]
    ),

    "zara": RetailerPattern(
        name="Zara",
        domain_patterns=["zara.com"],
        add_to_cart_selectors=[
            "button[class*='add']",
            "button:has-text('Add')",
            "[data-qa-action='add-to-cart']",
            "button[type='submit']"
        ],
        price_selectors=[
            "[class*='price']",
            ".price__amount",
            "span[class*='money']"
        ],
        out_of_stock_patterns=[
            "out of stock",
            "agotado",  # Spanish
            "not available"
        ],
        product_title_selectors=[
            "h1[class*='product-detail']",
            "h1"
        ]
    ),

    "hm": RetailerPattern(
        name="H&M",
        domain_patterns=["hm.com", "hm2.com"],
        add_to_cart_selectors=[
            "[data-test='add-to-bag']",
            "button[id*='add']:has-text('bag')",
            "button:has-text('Add to bag')"
        ],
        price_selectors=[
            "[class*='price']",
            "[data-test='price']"
        ],
        out_of_stock_patterns=[
            "out of stock",
            "sold out"
        ],
        product_title_selectors=[
            "h1[class*='title']",
            "h1"
        ]
    ),

    "nike": RetailerPattern(
        name="Nike",
        domain_patterns=["nike.com"],
        add_to_cart_selectors=[
            ".add-to-cart-btn",
            "button[data-test='add-to-cart']",
            "button:has-text('Add to Cart')",
            "[aria-label*='Add to Cart']"
        ],
        price_selectors=[
            "[data-test='product-price']",
            "[class*='product-price']",
            ".product-price"
        ],
        out_of_stock_patterns=[
            "out of stock",
            "sold out",
            "notify me"
        ],
        product_title_selectors=[
            "h1[data-test='product-title']",
            "h1[id='pdp_product_title']"
        ]
    ),

    "adidas": RetailerPattern(
        name="Adidas",
        domain_patterns=["adidas.com"],
        add_to_cart_selectors=[
            "[data-auto-id='add-to-bag']",
            "button:has-text('Add to Bag')"
        ],
        price_selectors=[
            "[class*='gl-price']",
            "[data-auto-id='product-price']"
        ],
        out_of_stock_patterns=[
            "out of stock",
            "sold out"
        ],
        product_title_selectors=[
            "h1[data-auto-id='product-title']"
        ]
    ),

    "gap": RetailerPattern(
        name="Gap",
        domain_patterns=["gap.com", "oldnavy.com", "bananarepublic.com"],
        add_to_cart_selectors=[
            "[data-test-id='add-to-bag-button']",
            "button:has-text('Add to Bag')"
        ],
        price_selectors=[
            "[class*='product__price']",
            "[data-test-id='product-price']"
        ],
        out_of_stock_patterns=[
            "out of stock",
            "sold out"
        ],
        product_title_selectors=[
            "h1[data-test-id='product-title']"
        ]
    ),

    "forever21": RetailerPattern(
        name="Forever 21",
        domain_patterns=["forever21.com"],
        add_to_cart_selectors=[
            "[data-option='add-to-cart']",
            "button:has-text('Add to Cart')"
        ],
        price_selectors=[
            "[class*='product-price']",
            ".price"
        ],
        out_of_stock_patterns=[
            "out of stock",
            "sold out"
        ],
        product_title_selectors=[
            "h1[class*='product-title']"
        ]
    ),

    "uniqlo": RetailerPattern(
        name="Uniqlo",
        domain_patterns=["uniqlo.com"],
        add_to_cart_selectors=[
            "[id*='addToCart']",
            "button:has-text('Add to Cart')"
        ],
        price_selectors=[
            "[class*='product-price']"
        ],
        out_of_stock_patterns=[
            "out of stock",
            "sold out"
        ],
        product_title_selectors=[
            "h1[class*='product-title']"
        ]
    ),

    "target": RetailerPattern(
        name="Target",
        domain_patterns=["target.com"],
        add_to_cart_selectors=[
            "[data-test='orderPickupButton']",
            "[data-test='shippingButton']",
            "button:has-text('Add to cart')"
        ],
        price_selectors=[
            "[data-test='product-price']",
            "span[class*='price']"
        ],
        out_of_stock_patterns=[
            "out of stock",
            "sold out",
            "not sold online"
        ],
        product_title_selectors=[
            "h1[data-test='product-title']"
        ]
    ),

    "walmart": RetailerPattern(
        name="Walmart",
        domain_patterns=["walmart.com"],
        add_to_cart_selectors=[
            "[data-automation-id='add-to-cart']",
            "button:has-text('Add to cart')"
        ],
        price_selectors=[
            "[itemprop='price']",
            "[class*='price-characteristic']"
        ],
        out_of_stock_patterns=[
            "out of stock",
            "sold out"
        ],
        product_title_selectors=[
            "h1[itemprop='name']"
        ]
    ),

    "amazon": RetailerPattern(
        name="Amazon",
        domain_patterns=["amazon.com", "amazon.co.uk", "amazon.ca"],
        add_to_cart_selectors=[
            "#add-to-cart-button",
            "[name='submit.add-to-cart']",
            "input[id='add-to-cart-button']"
        ],
        price_selectors=[
            ".a-price-whole",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "[class*='a-price']"
        ],
        out_of_stock_patterns=[
            "currently unavailable",
            "out of stock",
            "temporarily out of stock"
        ],
        product_title_selectors=[
            "#productTitle",
            "h1[id='title']"
        ]
    ),
}


# Universal Fallback Patterns (for unknown retailers)
UNIVERSAL_PATTERNS = RetailerPattern(
    name="Universal",
    domain_patterns=["*"],  # Matches any domain
    add_to_cart_selectors=[
        # Text-based selectors (language-agnostic)
        "button:has-text('Add to Cart')",
        "button:has-text('Add to Bag')",
        "button:has-text('Add to Basket')",
        "button:has-text('Buy Now')",
        "button:has-text('Purchase')",
        # Class-based patterns
        "[class*='add-to-cart']",
        "[class*='add-to-bag']",
        "[class*='addtocart']",
        "[class*='buy-button']",
        "[class*='purchase-button']",
        # ID-based patterns
        "[id*='add-to-cart']",
        "[id*='addToCart']",
        "[id*='buy-now']",
        # Data attribute patterns
        "[data-test*='add']",
        "[data-testid*='add']",
        "[data-qa*='add']",
        # ARIA labels
        "[aria-label*='Add to Cart']",
        "[aria-label*='Add to Bag']",
        # Generic button with cart-related text
        "button[type='submit']:has-text('cart')",
        "button[type='submit']:has-text('bag')"
    ],
    price_selectors=[
        # Class-based
        "[class*='price']",
        "[class*='product-price']",
        "[class*='current-price']",
        "[class*='sale-price']",
        # ID-based
        "[id*='price']",
        # Data attributes
        "[data-test*='price']",
        "[data-testid*='price']",
        "[data-price]",
        # Schema.org microdata
        "[itemprop='price']",
        "[itemtype*='Offer'] [itemprop='price']",
        # Generic patterns
        "span:has-text('$')",
        "div:has-text('$')",
        ".money",
        ".amount"
    ],
    out_of_stock_patterns=[
        # English
        "out of stock",
        "sold out",
        "unavailable",
        "not available",
        "currently unavailable",
        "temporarily unavailable",
        "notify me",
        "notify when available",
        "join waitlist",
        # Spanish
        "agotado",
        "no disponible",
        # French
        "épuisé",
        "non disponible",
        # German
        "ausverkauft",
        "nicht verfügbar"
    ],
    product_title_selectors=[
        "h1[class*='product']",
        "h1[class*='title']",
        "h1[data-test*='title']",
        "h1[itemprop='name']",
        "h1",  # Last resort: any h1
    ]
)


def detect_retailer(url: str) -> RetailerPattern:
    """
    Detect retailer from URL and return appropriate patterns.

    Args:
        url: Product URL

    Returns:
        RetailerPattern for the detected retailer or universal fallback
    """
    url_lower = url.lower()

    # Check against known retailers
    for retailer_id, pattern in RETAILER_PATTERNS.items():
        for domain_pattern in pattern.domain_patterns:
            if domain_pattern in url_lower:
                return pattern

    # Return universal fallback
    return UNIVERSAL_PATTERNS


def extract_domain(url: str) -> str:
    """
    Extract domain from URL.

    Args:
        url: Full URL

    Returns:
        Domain name (e.g., "nordstrom.com")
    """
    match = re.search(r'https?://(?:www\.)?([^/]+)', url)
    return match.group(1) if match else url


def is_out_of_stock_text(text: str, patterns: List[str]) -> bool:
    """
    Check if text indicates product is out of stock.

    Args:
        text: Text to check
        patterns: List of out-of-stock patterns

    Returns:
        True if text matches any out-of-stock pattern
    """
    text_lower = text.lower()
    return any(pattern.lower() in text_lower for pattern in patterns)


def get_all_selectors(pattern: RetailerPattern, selector_type: str) -> List[str]:
    """
    Get all selectors of a specific type for a retailer.

    Combines retailer-specific selectors with universal fallbacks.

    Args:
        pattern: Retailer pattern
        selector_type: Type of selector ('add_to_cart', 'price', 'product_title')

    Returns:
        Combined list of selectors
    """
    retailer_selectors = getattr(pattern, f"{selector_type}_selectors", [])
    universal_selectors = getattr(UNIVERSAL_PATTERNS, f"{selector_type}_selectors", [])

    # Combine retailer-specific + universal, avoiding duplicates
    combined = list(retailer_selectors)
    for selector in universal_selectors:
        if selector not in combined:
            combined.append(selector)

    return combined
