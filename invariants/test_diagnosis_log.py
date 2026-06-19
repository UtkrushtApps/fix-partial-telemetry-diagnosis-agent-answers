"""Verifies a durable, traceable diagnosis record is persisted with the
completeness signal. Does not call the model; inserts via the db helper.
"""
from __future__ import annotations

import uuid

import pytest

from agent import db


def test_diagnosis_log_records_completeness():
    trace_id = f"test-{uuid.uuid4()}"
    db.insert_diagnosis_log(
        trace_id=trace_id,
        device_id="dev-200",
        overall_status="degraded",
        data_complete=False,
        summary="Gateway offline; health not confirmed.",
    )
    with db.get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT overall_status, data_complete FROM diagnosis_log WHERE trace_id = %s",
            (trace_id,),
        )
        row = cur.fetchone()
    assert row is not None
    row = dict(row)
    assert row["overall_status"] == "degraded"
    assert row["data_complete"] is False

