"""Disk-backed cache wrapper for L0 connectors.

Thin abstraction over diskcache.Cache providing:
- Context manager support
- Typed get/set with default TTL
- Key namespacing per connector (optional)

Design: synchronous API (diskcache is thread-safe, not async-native).
When needed in async hot path, wrap with asyncio.to_thread in caller.
"""

from pathlib import Path
from typing import Any

import diskcache
import structlog

log = structlog.get_logger()

DEFAULT_TTL_SECONDS = 86400  # 24h — matches daily data source cadence


class ConnectorCache:
    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache = diskcache.Cache(str(self.cache_dir))

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL_SECONDS) -> None:
        self._cache.set(key, value, expire=ttl)
        log.debug("cache.set", key=key, ttl=ttl)

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def close(self) -> None:
        self._cache.close()

    def __enter__(self) -> "ConnectorCache":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
