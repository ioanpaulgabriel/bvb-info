"""
bvb_paper API - read-only endpoint for the current approval batch.
"""

from __future__ import annotations

import logging
import uuid
import os
from decimal import Decimal
from typing import Any

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

load_dotenv()

logger = logging.getLogger("bvb_paper")

DATABASE_URL = os.getenv("BVB_DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("BVB_DATABASE_URL is not configured")

DATABASE_URL = DATABASE_URL.replace(
    "postgresql+psycopg2://",
    "postgresql://",
)

app = FastAPI(
    title="bvb_paper API",
    version="1.0.1",
    description="Read-only API for BVB virtual paper-trading approval batches.",
)

SCHEMA_VERSION = 1
STOP_ATR_MULTIPLIER = 3.0


def json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def fetch_current_batch() -> dict[str, Any]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    batch_id,
                    signal_date,
                    status,
                    strategy_version,
                    created_at,
                    finalized_at
                FROM paper.approval_batches
                WHERE status = 'OPEN'
                ORDER BY signal_date DESC, created_at DESC
                LIMIT 1
                """
            )

            batch_row = cur.fetchone()

            if batch_row is None:
                return {
                    "schema_version": SCHEMA_VERSION,
                    "batch_id": None,
                    "signal_date": None,
                    "status": "EMPTY",
                    "strategy_version": None,
                    "created_at": None,
                    "finalized_at": None,
                    "counts": {
                        "pending": 0,
                        "approved": 0,
                        "rejected": 0,
                        "executed": 0,
                        "total": 0,
                    },
                    "orders": [],
                }

            (
                batch_id,
                signal_date,
                batch_status,
                strategy_version,
                created_at,
                finalized_at,
            ) = batch_row

            cur.execute(
                """
                SELECT
                    order_id,
                    symbol,
                    signal_date,
                    entry_date,
                    entry_price,
                    atr_value,
                    candidate_status,
                    strategy_version,
                    proposed_quantity,
                    approved_quantity,
                    status,
                    created_at
                FROM paper.orders
                WHERE batch_id = %s
                ORDER BY symbol ASC, created_at ASC
                """,
                (batch_id,),
            )

            rows = cur.fetchall()

    orders: list[dict[str, Any]] = []

    for row in rows:
        (
            order_id,
            symbol,
            order_signal_date,
            entry_date,
            entry_price,
            atr_value,
            candidate_status,
            order_strategy_version,
            proposed_quantity,
            approved_quantity,
            order_status,
            order_created_at,
        ) = row

        stop_price = None
        notional_value = None

        if entry_price is not None and atr_value is not None:
            stop_price = float(entry_price) - (
                STOP_ATR_MULTIPLIER * float(atr_value)
            )

        if proposed_quantity is not None and entry_price is not None:
            notional_value = float(proposed_quantity) * float(entry_price)

        orders.append(
            {
                "order_id": str(order_id),
                "symbol": symbol,
                "signal_date": order_signal_date.isoformat(),
                "entry_date": entry_date.isoformat() if entry_date else None,
                "entry_price": json_value(entry_price),
                "atr_value": json_value(atr_value),
                "stop_price": stop_price,
                "candidate_status": candidate_status,
                "proposed_quantity": int(proposed_quantity),
                "approved_quantity": (
                    int(approved_quantity)
                    if approved_quantity is not None
                    else None
                ),
                "status": order_status,
                "notional_value": notional_value,
                "reason": candidate_status,
                "strategy_version": order_strategy_version,
                "created_at": (
                    order_created_at.isoformat()
                    if order_created_at
                    else None
                ),
            }
        )

    counts = {
        "pending": sum(
            1 for order in orders
            if order["status"] == "PENDING_APPROVAL"
        ),
        "approved": sum(
            1 for order in orders
            if order["status"] == "APPROVED"
        ),
        "rejected": sum(
            1 for order in orders
            if order["status"] == "REJECTED"
        ),
        "executed": sum(
            1 for order in orders
            if order["status"] == "EXECUTED"
        ),
        "total": len(orders),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "batch_id": str(batch_id),
        "signal_date": signal_date.isoformat(),
        "status": batch_status,
        "strategy_version": strategy_version,
        "created_at": created_at.isoformat() if created_at else None,
        "finalized_at": finalized_at.isoformat() if finalized_at else None,
        "counts": counts,
        "orders": orders,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "bvb_paper"}


@app.get("/paper/batches/current")
def get_current_batch():
    try:
        payload = fetch_current_batch()
    except psycopg.Error:
        logger.exception("Paper database query failed")

        raise HTTPException(
            status_code=503,
            detail="Paper database query failed",
        )

    return JSONResponse(content=payload)


@app.post("/paper/orders/{order_id:uuid}/approve")
def approve_order(
    order_id: uuid.UUID,
    payload: dict[str, Any],
):
    approved_quantity = payload.get("approved_quantity")

    if approved_quantity is None:
        raise HTTPException(
            status_code=422,
            detail="approved_quantity is required",
        )

    try:
        approved_quantity = int(approved_quantity)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail="approved_quantity must be an integer",
        )

    if approved_quantity <= 0:
        raise HTTPException(
            status_code=422,
            detail="approved_quantity must be greater than zero",
        )

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT paper.approve_order(
                        %s::uuid,
                        %s::numeric
                    )
                    """,
                    (order_id, approved_quantity),
                )
    except psycopg.Error:
        logger.exception("Failed to approve paper order")

        raise HTTPException(
            status_code=503,
            detail="Paper database query failed",
        )

    return {
        "order_id": order_id,
        "status": "APPROVED",
        "approved_quantity": approved_quantity,
    }


@app.post("/paper/orders/{order_id:uuid}/reject")
def reject_order(
    order_id: uuid.UUID,
):
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT paper.reject_order(%s::uuid)
                    """,
                    (order_id,),
                )
    except psycopg.Error:
        logger.exception("Failed to reject paper order")

        raise HTTPException(
            status_code=503,
            detail="Paper database query failed",
        )

    return {
        "order_id": order_id,
        "status": "REJECTED",
    }


@app.post("/paper/batches/{batch_id:uuid}/finalize")
def finalize_batch(
    batch_id: uuid.UUID,
):
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT paper.finalize_batch(%s::uuid)
                    """,
                    (batch_id,),
                )
    except psycopg.Error:
        logger.exception("Failed to finalize paper batch")

        raise HTTPException(
            status_code=503,
            detail="Paper database query failed",
        )

    return {
        "batch_id": str(batch_id),
        "status": "FINALIZED",
    }


@app.post("/paper/orders/{order_id:uuid}/execute")
def execute_order(
    order_id: uuid.UUID,
    payload: dict[str, Any],
):
    execution_price = payload.get("execution_price")
    execution_date = payload.get("execution_date")

    if execution_price is None:
        raise HTTPException(
            status_code=422,
            detail="execution_price is required",
        )

    if execution_date is None:
        raise HTTPException(
            status_code=422,
            detail="execution_date is required",
        )

    try:
        execution_price = float(execution_price)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail="execution_price must be a number",
        )

    if execution_price <= 0:
        raise HTTPException(
            status_code=422,
            detail="execution_price must be greater than zero",
        )

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT paper.execute_order(
                        %s::uuid,
                        %s::numeric,
                        %s::date
                    )
                    """,
                    (order_id, execution_price, execution_date),
                )
    except psycopg.Error:
        logger.exception("Failed to execute paper order")

        raise HTTPException(
            status_code=503,
            detail="Paper database query failed",
        )

    return {
        "order_id": str(order_id),
        "status": "EXECUTED",
        "execution_price": execution_price,
        "execution_date": execution_date,
    }
