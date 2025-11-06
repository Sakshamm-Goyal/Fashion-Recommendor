# integrations/affiliate_manager.py
"""
Affiliate Link Management for monetization (OPTIONAL).

This module is completely optional. If affiliate keys are not configured,
the system will work perfectly fine without affiliate links.

For production monetization, you can sign up for affiliate programs:
- Rakuten Advertising (Macy's, Nordstrom, Bloomingdale's)
- Impact.com (premium brands)
- ShareASale (boutique retailers)

But this is NOT required for the core recommendation pipeline.
"""
from typing import Optional, Dict
from urllib.parse import urlparse, urlencode
import config


def convert_to_affiliate_link(product_url: str, retailer: Optional[str] = None) -> tuple[Optional[str], float]:
    """
    Convert product URL to affiliate link (OPTIONAL - returns None if not configured).

    Args:
        product_url: Original product URL
        retailer: Optional retailer name

    Returns:
        Tuple of (affiliate_link or None, commission_rate)
        If affiliate networks are not configured, returns (None, 0.0)
    """
    # Check if any affiliate keys are configured
    has_rakuten = getattr(config, "RAKUTEN_API_KEY", None)
    has_impact = getattr(config, "IMPACT_API_KEY", None)
    has_sharesale = getattr(config, "SHARESALE_AFFILIATE_ID", None)

    if not (has_rakuten or has_impact or has_sharesale):
        # No affiliate networks configured - return original URL
        return (None, 0.0)

    # If configured, try to generate affiliate link
    try:
        manager = AffiliateManager()
        return manager.convert_to_affiliate_link(product_url, retailer)
    except Exception:
        # Gracefully handle any affiliate conversion failures
        return (None, 0.0)


class AffiliateManager:
    """
    Manages affiliate link generation and tracking.
    """

    def __init__(self):
        """Initialize affiliate manager with network configurations."""

        # Rakuten Advertising configuration
        self.rakuten_config = {
            "api_key": getattr(config, "RAKUTEN_API_KEY", None),
            "account_id": getattr(config, "RAKUTEN_ACCOUNT_ID", None),
            "networks": {
                "macys.com": {"merchant_id": "12345", "commission_rate": 0.05},
                "nordstrom.com": {"merchant_id": "67890", "commission_rate": 0.04},
                "bloomingdales.com": {"merchant_id": "11111", "commission_rate": 0.05},
            }
        }

        # Impact.com configuration
        self.impact_config = {
            "api_key": getattr(config, "IMPACT_API_KEY", None),
            "account_id": getattr(config, "IMPACT_ACCOUNT_ID", None),
            "networks": {
                "nike.com": {"campaign_id": "9999", "commission_rate": 0.08},
                "adidas.com": {"campaign_id": "8888", "commission_rate": 0.07},
            }
        }

        # ShareASale configuration
        self.sharesale_config = {
            "affiliate_id": getattr(config, "SHARESALE_AFFILIATE_ID", None),
            "networks": {
                "urbanoutfitters.com": {"merchant_id": "55555", "commission_rate": 0.06},
                "revolve.com": {"merchant_id": "66666", "commission_rate": 0.05},
            }
        }

        # Commission rates for known retailers (default)
        self.default_commission_rates = {
            "zara.com": 0.04,
            "hm.com": 0.04,
            "asos.com": 0.06,
            "amazon.com": 0.04,
        }

    def convert_to_affiliate_link(
        self,
        product_url: str,
        retailer: Optional[str] = None
    ) -> tuple[str, float]:
        """
        Convert a product URL to an affiliate link.

        Args:
            product_url: Original product URL
            retailer: Retailer name (optional, will be extracted from URL)

        Returns:
            Tuple of (affiliate_link, commission_rate)
        """
        # Extract domain from URL
        try:
            domain = urlparse(product_url).netloc.replace("www.", "")
        except Exception:
            return product_url, 0.0

        # Check which network handles this retailer
        affiliate_link = product_url
        commission_rate = self.default_commission_rates.get(domain, 0.03)

        # Try Rakuten network
        if domain in self.rakuten_config["networks"]:
            affiliate_link = self._generate_rakuten_link(product_url, domain)
            commission_rate = self.rakuten_config["networks"][domain]["commission_rate"]

        # Try Impact.com network
        elif domain in self.impact_config["networks"]:
            affiliate_link = self._generate_impact_link(product_url, domain)
            commission_rate = self.impact_config["networks"][domain]["commission_rate"]

        # Try ShareASale network
        elif domain in self.sharesale_config["networks"]:
            affiliate_link = self._generate_sharesale_link(product_url, domain)
            commission_rate = self.sharesale_config["networks"][domain]["commission_rate"]

        # For other retailers, check if we have generic commission info
        else:
            # Return original link (no affiliate tracking)
            commission_rate = self.default_commission_rates.get(domain, 0.0)

        return affiliate_link, commission_rate

    def _generate_rakuten_link(self, url: str, domain: str) -> str:
        """Generate Rakuten affiliate link."""
        if not self.rakuten_config["account_id"]:
            return url

        merchant_id = self.rakuten_config["networks"][domain]["merchant_id"]

        # Rakuten link format: https://click.linksynergy.com/deeplink?id={account_id}&mid={merchant_id}&murl={encoded_url}
        params = {
            "id": self.rakuten_config["account_id"],
            "mid": merchant_id,
            "murl": url
        }
        return f"https://click.linksynergy.com/deeplink?{urlencode(params)}"

    def _generate_impact_link(self, url: str, domain: str) -> str:
        """Generate Impact.com affiliate link."""
        if not self.impact_config["account_id"]:
            return url

        campaign_id = self.impact_config["networks"][domain]["campaign_id"]

        # Impact link format: https://imp.i{account_id}.net/c/{campaign_id}/{account_id}/{encoded_url}
        account_id = self.impact_config["account_id"]
        return f"https://imp.i{account_id}.net/c/{campaign_id}/{account_id}/0?u={url}"

    def _generate_sharesale_link(self, url: str, domain: str) -> str:
        """Generate ShareASale affiliate link."""
        if not self.sharesale_config["affiliate_id"]:
            return url

        merchant_id = self.sharesale_config["networks"][domain]["merchant_id"]

        # ShareASale link format: https://shareasale.com/r.cfm?b={merchant_id}&u={affiliate_id}&m={merchant_id}&urllink={url}
        params = {
            "b": merchant_id,
            "u": self.sharesale_config["affiliate_id"],
            "m": merchant_id,
            "urllink": url
        }
        return f"https://shareasale.com/r.cfm?{urlencode(params)}"

    def get_commission_rate(self, retailer: str) -> float:
        """
        Get expected commission rate for a retailer.

        Args:
            retailer: Retailer name or domain

        Returns:
            Commission rate as decimal (0.05 = 5%)
        """
        # Normalize retailer name
        retailer_lower = retailer.lower()

        # Check all networks
        for network in [self.rakuten_config, self.impact_config, self.sharesale_config]:
            for domain, config in network.get("networks", {}).items():
                if retailer_lower in domain or domain in retailer_lower:
                    return config["commission_rate"]

        # Return default
        return self.default_commission_rates.get(retailer_lower, 0.03)

    def enrich_product_with_affiliate(self, product: Dict) -> Dict:
        """
        Enrich a product dict with affiliate link and commission info.

        Args:
            product: Product dict with 'url' and 'retailer'

        Returns:
            Product dict with 'affiliate_link' and 'commission_rate' added
        """
        if "url" not in product:
            return product

        affiliate_link, commission_rate = self.convert_to_affiliate_link(
            product["url"],
            product.get("retailer")
        )

        product["affiliate_link"] = affiliate_link
        product["commission_rate"] = commission_rate

        return product


# Global singleton instance
_affiliate_manager = None


def get_affiliate_manager() -> AffiliateManager:
    """Get or create global affiliate manager instance."""
    global _affiliate_manager
    if _affiliate_manager is None:
        _affiliate_manager = AffiliateManager()
    return _affiliate_manager


# Convenience functions
def convert_to_affiliate_link(url: str, retailer: Optional[str] = None) -> tuple[str, float]:
    """Quick function to convert URL to affiliate link."""
    manager = get_affiliate_manager()
    return manager.convert_to_affiliate_link(url, retailer)


def enrich_product_with_affiliate(product: Dict) -> Dict:
    """Quick function to enrich product with affiliate data."""
    manager = get_affiliate_manager()
    return manager.enrich_product_with_affiliate(product)
