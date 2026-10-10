"""Postgres connection pool and a tiny SQL migration runner."""

from __future__ import annotations

import logging
from pathlib import Path

from pgvector.psycopg import register_vector
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

log = logging.getLogger(__name__)
MIGRATIONS = Path(__file__).parent / "migrations"
_pool: ConnectionPool | None = None


def _configure(conn: Connection) -> None:
    try:
        register_vector(conn)
    except Exception:  # extension not created yet (first boot, before migrations)
        pass


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            settings().database_url,
            min_size=1,
            max_size=8,
            kwargs={"row_factory": dict_row, "autocommit": True},
            configure=_configure,
            # Serverless Postgres (Neon) closes idle connections; check before handing one out.
            check=ConnectionPool.check_connection,
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def migrate() -> list[str]:
    """Apply pending migrations in name order. Each file runs in its own transaction."""
    applied: list[str] = []
    with pool().connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz DEFAULT now())"
        )
        done = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations").fetchall()}
        for f in sorted(MIGRATIONS.glob("*.sql")):
            if f.name in done:
                continue
            with conn.transaction():
                conn.execute(f.read_text())
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (f.name,))
            applied.append(f.name)
            log.info("migration applied: %s", f.name)
    # The vector type exists now; make sure pooled connections know about it.
    close_pool()
    return applied
