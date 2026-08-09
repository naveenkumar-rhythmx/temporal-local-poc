"""Read-only PostgreSQL access for the patient dashboard APIs."""

from __future__ import annotations

import datetime as dt
import os
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row


def db_dsn() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://patient_app:local-only-change-me@app-postgres.patient-data-services.svc.cluster.local:5432/patient_db",
    )


def _jsonable(value: Any) -> Any:
    """Convert psycopg types (Decimal/date) into JSON-serialisable values."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def query(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with psycopg.connect(db_dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [_jsonable(dict(row)) for row in rows]


def query_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def ping() -> bool:
    try:
        query("SELECT 1 AS ok")
        return True
    except Exception:  # noqa: BLE001
        return False
