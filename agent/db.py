"""PostgreSQL helpers for telemetry retrieval and diagnosis logging.

Uses psycopg (v3) when available, falling back to psycopg2 so the scaffold
loads and runs regardless of which driver the runtime provides.
"""
from __future__ import annotations

from typing import Any

from agent.config import config

_DRIVER = None
try:  # Prefer psycopg (v3)
    import psycopg  # type: ignore
    from psycopg.rows import dict_row  # type: ignore
    _DRIVER = "psycopg3"
except Exception:  # noqa: BLE001
    try:
        import psycopg2  # type: ignore
        import psycopg2.extras  # type: ignore
        _DRIVER = "psycopg2"
    except Exception:  # noqa: BLE001
        _DRIVER = None


class _Psycopg2DictConnection:
    """Thin wrapper so psycopg2 cursors yield dict-like rows and support the
    same context-manager usage as psycopg3 in this codebase."""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def commit(self):
        return self._conn.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()
        return False


def get_connection():
    if _DRIVER == "psycopg3":
        return psycopg.connect(config.DATABASE_URL, row_factory=dict_row)
    if _DRIVER == "psycopg2":
        return _Psycopg2DictConnection(psycopg2.connect(config.DATABASE_URL))
    raise RuntimeError(
        "No PostgreSQL driver available. Install psycopg or psycopg2-binary."
    )


def fetch_device(device_id: str) -> dict[str, Any] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT device_id, model, gateway_id FROM devices WHERE device_id = %s",
            (device_id,),
        )
        row = cur.fetchone()
        return dict(row) if row is not None else None


def fetch_latest_sensor_reading(device_id: str) -> dict[str, Any] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT device_id, status, temperature_c, battery_pct, recorded_at
            FROM sensor_readings
            WHERE device_id = %s
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
            (device_id,),
        )
        row = cur.fetchone()
        return dict(row) if row is not None else None


def fetch_latest_gateway_status(gateway_id: str) -> dict[str, Any] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT gateway_id, status, uplink_ok, recorded_at
            FROM gateway_status
            WHERE gateway_id = %s
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
            (gateway_id,),
        )
        row = cur.fetchone()
        return dict(row) if row is not None else None


def insert_diagnosis_log(trace_id: str,
                         device_id: str,
                         overall_status: str | None,
                         data_complete: bool | None,
                         summary: str | None) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO diagnosis_log
                (trace_id, device_id, overall_status, data_complete, summary)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (trace_id, device_id, overall_status, data_complete, summary),
        )
        conn.commit()


def db_smoke_check() -> bool:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM devices")
        row = cur.fetchone()
        return bool(row and dict(row)["n"] >= 1)

