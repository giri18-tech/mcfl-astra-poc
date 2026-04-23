"""
asyncpg pool for Aurora/PostgreSQL.

The API remains usable without a live database: callers probe connectivity
with `ping_postgres()` and fall back to mock payloads when appropriate.
"""

from __future__ import annotations

import asyncio
import ssl
from typing import Optional

import asyncpg

from config.settings import settings

# Process-wide pool; Lambda reuse benefits from a single warm pool per execution environment.
_pool: Optional[asyncpg.Pool] = None


def _ssl_context() -> ssl.SSLContext | None:
    """Aurora typically requires TLS; local dev often runs without it."""
    if settings.DB_SSL.lower() in ("require", "true", "1"):
        return ssl.create_default_context()
    return None


async def get_pool() -> asyncpg.Pool:
    """Lazily construct (or return) the asyncpg pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            ssl=_ssl_context(),
            min_size=1,
            max_size=2,
        )
    return _pool


async def close_pool() -> None:
    """Close the pool (e.g. after a failed health check so the next call can retry)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def ping_postgres() -> bool:
    """
    Return True only if we can open a connection and run a trivial query.

    Any failure (network, auth, timeout) returns False so the service layer
    can serve the mock litigation contract instead of erroring.
    """
    try:
        pool = await asyncio.wait_for(get_pool(), timeout=settings.DB_CONNECT_TIMEOUT_SECONDS)
        async with pool.acquire() as conn:
            value = await conn.fetchval("SELECT 1")
            return value == 1
    except Exception:
        await close_pool()
        return False
