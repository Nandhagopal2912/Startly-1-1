"""Redis cache configuration and utilities"""

import os
import json
from datetime import timedelta
from typing import Any, Optional
import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", 86400))  # 24 hours default

# Initialize Redis connection (lazy initialization to handle connection errors gracefully)
redis_client = None

def get_redis_client():
    """Get Redis client, initializing if necessary"""
    global redis_client
    if redis_client is None:
        try:
            redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        except Exception as e:
            print(f"Warning: Redis connection failed: {e}. Caching will be disabled.")
            redis_client = None
    return redis_client


def test_redis_connection():
    """Test Redis connection"""
    try:
        client = get_redis_client()
        if client:
            client.ping()
            print("✓ Redis connection successful")
            return True
        else:
            print("✗ Redis client not available")
            return False
    except Exception as e:
        print(f"✗ Redis connection failed: {e}")
        return False


def get_cache(key: str) -> Optional[Any]:
    """Get value from cache"""
    try:
        client = get_redis_client()
        if not client:
            return None
        data = client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        print(f"Error getting cache: {e}")
        return None


def set_cache(key: str, value: Any, ttl: int = CACHE_TTL) -> bool:
    """Set value in cache with TTL"""
    try:
        client = get_redis_client()
        if not client:
            return False
        client.setex(key, ttl, json.dumps(value))
        return True
    except Exception as e:
        print(f"Error setting cache: {e}")
        return False


def delete_cache(key: str) -> bool:
    """Delete value from cache"""
    try:
        client = get_redis_client()
        if not client:
            return False
        client.delete(key)
        return True
    except Exception as e:
        print(f"Error deleting cache: {e}")
        return False


def clear_user_cache(user_id: str) -> int:
    """Clear all cache entries for a specific user"""
    try:
        client = get_redis_client()
        if not client:
            return 0
        pattern = f"user:{user_id}:*"
        keys = client.keys(pattern)
        if keys:
            return client.delete(*keys)
        return 0
    except Exception as e:
        print(f"Error clearing user cache: {e}")
        return 0


def cache_user_data(user_id: str, data: dict) -> bool:
    """Cache user data"""
    key = f"user:{user_id}:profile"
    return set_cache(key, data, ttl=3600)  # 1 hour


def get_user_cache(user_id: str) -> Optional[dict]:
    """Get cached user data"""
    key = f"user:{user_id}:profile"
    return get_cache(key)


def cache_search_result(user_id: str, keyword: str, result: dict) -> bool:
    """Cache search result - replaces local file caching"""
    key = f"user:{user_id}:search:{keyword.lower().replace(' ', '_')}"
    return set_cache(key, result, ttl=CACHE_TTL)


def get_search_cache(user_id: str, keyword: str) -> Optional[dict]:
    """Get cached search result"""
    key = f"user:{user_id}:search:{keyword.lower().replace(' ', '_')}"
    return get_cache(key)


def cache_serp_analysis(hash_key: str, analysis: dict) -> bool:
    """Cache SERP analysis by hash"""
    key = f"serp:analysis:{hash_key}"
    return set_cache(key, analysis, ttl=CACHE_TTL)


def get_serp_analysis(hash_key: str) -> Optional[dict]:
    """Get cached SERP analysis"""
    key = f"serp:analysis:{hash_key}"
    return get_cache(key)
