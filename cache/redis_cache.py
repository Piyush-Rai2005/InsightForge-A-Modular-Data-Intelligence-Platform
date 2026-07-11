"""
Redis cache wrapper with automatic in-memory fallback when Redis is unavailable.
Used for: query results caching, job status tracking, job result storage.
"""
import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DEFAULT_TTL = 3600  # 1 hour


class _Cache:
    """Unified cache interface — tries Redis, falls back to dict."""

    def __init__(self):
        self._redis = None
        self._memory = {}
        self._connect()

    def _connect(self):
        try:
            import redis
            self._redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
            self._redis.ping()
            logger.info("Redis connected at %s", REDIS_URL)
        except Exception as e:
            logger.warning("Redis unavailable (%s) — using in-memory cache", e)
            self._redis = None

    # ── Core ops ────────────────────────────────────────────────────────────
    def get(self, key: str) -> Optional[str]:
        if self._redis:
            return self._redis.get(key)
        return self._memory.get(key)

    def set(self, key: str, value: str, ttl: int = DEFAULT_TTL):
        if self._redis:
            self._redis.setex(key, ttl, value)
        else:
            self._memory[key] = value

    def delete(self, key: str):
        if self._redis:
            self._redis.delete(key)
        else:
            self._memory.pop(key, None)

    # ── JSON helpers ────────────────────────────────────────────────────────
    def get_json(self, key: str):
        raw = self.get(key)
        return json.loads(raw) if raw else None

    def set_json(self, key: str, data, ttl: int = DEFAULT_TTL):
        self.set(key, json.dumps(data, default=str), ttl)

    # ── Job-specific helpers ────────────────────────────────────────────────
    def set_job_status(self, job_id: str, status: str, step: str = "", progress: float = 0):
        self.set_json(f"job:{job_id}:status", {
            "status": status, "step": step, "progress": progress,
        }, ttl=600)

    def get_job_status(self, job_id: str):
        return self.get_json(f"job:{job_id}:status")

    def set_job_result(self, job_id: str, result: dict):
        self.set_json(f"job:{job_id}:result", result, ttl=3600)

    def get_job_result(self, job_id: str):
        return self.get_json(f"job:{job_id}:result")


cache = _Cache()
