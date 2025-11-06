# infra/cache.py
"""
Redis caching layer for weather, product searches, and LLM outputs.
"""
import redis
import json
import config

_r = redis.Redis.from_url(config.REDIS_URL, decode_responses=True)


def cache_get(key):
    """
    Retrieve a value from Redis cache.
    Returns None if key doesn't exist.
    """
    v = _r.get(key)
    return json.loads(v) if v else None


def cache_set(key, value, ttl=3600):
    """
    Store a value in Redis cache with TTL in seconds.
    Default TTL is 1 hour.
    """
    _r.setex(key, ttl, json.dumps(value))


def cache_delete(key):
    """
    Delete a key from Redis cache.
    """
    _r.delete(key)
