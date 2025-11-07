"""
Link Verification Cache for Elara Fashion Recommendation System

Redis-based caching layer for verified product links.
Reduces redundant verification checks and improves response times.

Features:
- Verified link caching (1 hour TTL)
- Automatic cache invalidation
- Fast lookups (< 1ms)
- Product metadata storage
- Batch operations

Author: Elara Team
"""

import asyncio
import json
import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import redis.asyncio as redis

from contracts.models import Product

logger = logging.getLogger(__name__)


class LinkVerificationCache:
    """
    Redis-based cache for verified product links.

    Caches verification results to avoid redundant browser checks.
    """

    def __init__(
        self,
        redis_url: str,
        default_ttl: int = 3600,  # 1 hour
        key_prefix: str = "elara:verified:"
    ):
        """
        Initialize cache.

        Args:
            redis_url: Redis connection URL
            default_ttl: Default cache TTL in seconds
            key_prefix: Prefix for all cache keys
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self._client: Optional[redis.Redis] = None

    async def connect(self):
        """Establish Redis connection"""
        try:
            self._client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._client.ping()
            logger.info("Link cache connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self._client = None

    async def close(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            logger.info("Link cache disconnected from Redis")

    def _make_key(self, url: str) -> str:
        """
        Generate cache key for URL.

        Args:
            url: Product URL

        Returns:
            Cache key
        """
        # Use URL as key (Redis handles hashing)
        return f"{self.key_prefix}{url}"

    async def get_cached_verification(
        self,
        url: str
    ) -> Optional[Product]:
        """
        Get cached verified product.

        Args:
            url: Product URL

        Returns:
            Product if cached and valid, None otherwise
        """
        if not self._client:
            return None

        try:
            key = self._make_key(url)
            data = await self._client.get(key)

            if data:
                # Deserialize product data
                product_dict = json.loads(data)
                product = Product(**product_dict)

                logger.debug(f"Cache HIT: {url[:60]}...")
                return product

            logger.debug(f"Cache MISS: {url[:60]}...")
            return None

        except Exception as e:
            logger.warning(f"Cache get error: {str(e)}")
            return None

    async def cache_verification(
        self,
        product: Product,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache verified product.

        Args:
            product: Verified product to cache
            ttl: Optional TTL override (seconds)

        Returns:
            True if cached successfully
        """
        if not self._client:
            return False

        try:
            key = self._make_key(product.url)
            ttl = ttl or self.default_ttl

            # Serialize product to JSON
            product_dict = product.model_dump()
            data = json.dumps(product_dict)

            # Store with TTL
            await self._client.setex(key, ttl, data)

            logger.debug(f"Cached: {product.url[:60]}... (TTL: {ttl}s)")
            return True

        except Exception as e:
            logger.warning(f"Cache set error: {str(e)}")
            return False

    async def cache_batch(
        self,
        products: List[Product],
        ttl: Optional[int] = None
    ) -> int:
        """
        Cache multiple verified products.

        Args:
            products: List of verified products
            ttl: Optional TTL override

        Returns:
            Number of products cached successfully
        """
        if not self._client or not products:
            return 0

        cached_count = 0
        for product in products:
            if await self.cache_verification(product, ttl):
                cached_count += 1

        logger.info(f"Batch cached: {cached_count}/{len(products)} products")
        return cached_count

    async def get_batch(
        self,
        urls: List[str]
    ) -> Dict[str, Product]:
        """
        Get multiple cached products.

        Args:
            urls: List of product URLs

        Returns:
            Dictionary mapping URL -> Product for cached items
        """
        if not self._client or not urls:
            return {}

        cached_products = {}

        # Use pipeline for efficient batch operations
        async with self._client.pipeline() as pipe:
            for url in urls:
                key = self._make_key(url)
                pipe.get(key)

            results = await pipe.execute()

        # Parse results
        for url, data in zip(urls, results):
            if data:
                try:
                    product_dict = json.loads(data)
                    product = Product(**product_dict)
                    cached_products[url] = product
                except Exception as e:
                    logger.warning(f"Failed to deserialize cached product: {str(e)}")

        hit_rate = len(cached_products) / len(urls) * 100 if urls else 0
        logger.info(
            f"Batch get: {len(cached_products)}/{len(urls)} cached "
            f"({hit_rate:.1f}% hit rate)"
        )

        return cached_products

    async def invalidate_cache(
        self,
        url: str
    ) -> bool:
        """
        Invalidate cached product.

        Args:
            url: Product URL

        Returns:
            True if invalidated successfully
        """
        if not self._client:
            return False

        try:
            key = self._make_key(url)
            deleted = await self._client.delete(key)

            if deleted:
                logger.info(f"Invalidated cache: {url[:60]}...")
                return True

            return False

        except Exception as e:
            logger.warning(f"Cache invalidation error: {str(e)}")
            return False

    async def invalidate_batch(
        self,
        urls: List[str]
    ) -> int:
        """
        Invalidate multiple cached products.

        Args:
            urls: List of product URLs

        Returns:
            Number of items invalidated
        """
        if not self._client or not urls:
            return 0

        try:
            keys = [self._make_key(url) for url in urls]
            deleted = await self._client.delete(*keys)

            logger.info(f"Batch invalidated: {deleted}/{len(urls)} items")
            return deleted

        except Exception as e:
            logger.warning(f"Batch invalidation error: {str(e)}")
            return 0

    async def get_cache_stats(self) -> Dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        if not self._client:
            return {"error": "Not connected"}

        try:
            # Get Redis info
            info = await self._client.info("stats")

            # Count Elara verification keys
            pattern = f"{self.key_prefix}*"
            cursor = 0
            key_count = 0

            while True:
                cursor, keys = await self._client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                key_count += len(keys)

                if cursor == 0:
                    break

            stats = {
                "cached_products": key_count,
                "total_redis_keys": info.get("db0", {}).get("keys", 0),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": (
                    info.get("keyspace_hits", 0) /
                    (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1))
                    * 100
                )
            }

            return stats

        except Exception as e:
            logger.error(f"Failed to get cache stats: {str(e)}")
            return {"error": str(e)}

    async def clear_all_verification_cache(self) -> int:
        """
        Clear all verification cache entries.

        WARNING: This clears ALL cached verifications.

        Returns:
            Number of keys deleted
        """
        if not self._client:
            return 0

        try:
            pattern = f"{self.key_prefix}*"
            deleted = 0

            cursor = 0
            while True:
                cursor, keys = await self._client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )

                if keys:
                    deleted += await self._client.delete(*keys)

                if cursor == 0:
                    break

            logger.warning(f"Cleared ALL verification cache: {deleted} keys deleted")
            return deleted

        except Exception as e:
            logger.error(f"Cache clear error: {str(e)}")
            return 0


# Async context manager support
class LinkVerificationCacheContext(LinkVerificationCache):
    """Link cache with async context manager support"""

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Global cache instance (initialized by application)
_cache_instance: Optional[LinkVerificationCache] = None


async def get_cache(redis_url: str) -> LinkVerificationCache:
    """
    Get or create global cache instance.

    Args:
        redis_url: Redis connection URL

    Returns:
        LinkVerificationCache instance
    """
    global _cache_instance

    if _cache_instance is None:
        _cache_instance = LinkVerificationCache(redis_url)
        await _cache_instance.connect()

    return _cache_instance


async def close_cache():
    """Close global cache instance"""
    global _cache_instance

    if _cache_instance:
        await _cache_instance.close()
        _cache_instance = None
