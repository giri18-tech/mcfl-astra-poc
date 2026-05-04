"""
pymssql connection for SQL Server.

pymssql ships FreeTDS statically linked in its PyPI wheel — no ODBC driver or Lambda
layer required. Synchronous FreeTDS calls are dispatched via run_in_executor so the
event loop stays unblocked between requests.
"""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Optional

import pymssql

from config.settings import settings

# Single persistent connection per Lambda execution environment.
# Lambda handles one request at a time per instance, so one connection is sufficient.
_conn: Optional[pymssql.Connection] = None


def _new_connection() -> pymssql.Connection:
    return pymssql.connect(
        server=settings.DB_HOST,
        port=str(settings.DB_PORT),
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        login_timeout=max(1, int(settings.DB_CONNECT_TIMEOUT_SECONDS)),
    )


async def get_connection() -> pymssql.Connection:
    """Lazily open (or return) the persistent connection."""
    global _conn
    if _conn is None:
        loop = asyncio.get_event_loop()
        _conn = await loop.run_in_executor(None, _new_connection)
    return _conn


async def close_connection() -> None:
    """Close and clear the connection so the next call reconnects cleanly."""
    global _conn
    if _conn is not None:
        conn, _conn = _conn, None
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, conn.close)


async def ping_db() -> bool:
    """
    Return True only if we can open a connection and run a trivial query.

    Any failure (network, auth, timeout) returns False so the service layer
    can serve the mock litigation contract instead of erroring.
    """
    try:
        conn = await asyncio.wait_for(
            get_connection(), timeout=settings.DB_CONNECT_TIMEOUT_SECONDS
        )

        def _check(c: pymssql.Connection) -> bool:
            with c.cursor() as cur:
                cur.execute("SELECT 1")
                row = cur.fetchone()
                return row is not None and row[0] == 1

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(_check, conn))
    except Exception:
        await close_connection()
        return False
