"""Admin REST API for model lifecycle and system configuration (Issue #160)."""

import glob
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.auth import require_admin_key
from config.settings import settings, _runtime_cache
from detection.model_registry import get_current_version, list_model_versions

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin_key)])

_MODEL_NAMES = ["random_forest", "xgboost", "lightgbm"]

# Rate limiter instance for the reset endpoint
_limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# GET /admin/models
# ---------------------------------------------------------------------------


@router.get("/models", include_in_schema=False)
def list_models() -> list[dict]:
    """List all versioned model files with active/inactive deployment status."""
    model_dir = settings.model_dir
    result: dict[str, dict] = {}

    for name in _MODEL_NAMES:
        current = get_current_version(name, model_dir)
        try:
            versions = list_model_versions(name, model_dir)
        except (FileNotFoundError, OSError):
            versions = []
        for v in versions:
            key = v
            if key not in result:
                result[key] = {"version": v, "models": [], "active": v == current}
            result[key]["models"].append(name)
            if v == current:
                result[key]["active"] = True

    return list(result.values())


# ---------------------------------------------------------------------------
# POST /admin/models/{version}/promote
# ---------------------------------------------------------------------------


@router.post("/models/{version}/promote", include_in_schema=False)
def promote_model(version: str) -> dict:
    """Promote ``version`` to active for all three model types."""
    model_dir = settings.model_dir
    missing = [
        name
        for name in _MODEL_NAMES
        if not os.path.isfile(os.path.join(model_dir, f"{name}_v{version}.joblib"))
    ]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Model files not found for version {version!r}: {missing}",
        )

    for name in _MODEL_NAMES:
        latest_path = os.path.join(model_dir, f"{name}_latest.txt")
        with open(latest_path, "w") as f:
            f.write(version)

    return {"promoted": version, "models": _MODEL_NAMES}


# ---------------------------------------------------------------------------
# GET /admin/config
# ---------------------------------------------------------------------------


@router.get("/config", include_in_schema=False)
def get_config() -> dict:
    """Return the current runtime configuration from the `runtime_config` table."""
    config: dict = {}
    try:
        with sqlite3.connect(settings.db_path) as conn:
            for key, value in conn.execute("SELECT key, value FROM runtime_config"):
                config[key] = value
    except sqlite3.OperationalError:
        pass
    return config


# ---------------------------------------------------------------------------
# PATCH /admin/config
# ---------------------------------------------------------------------------


class ConfigPatch(BaseModel):
    updates: dict[str, str]


@router.patch("/config", include_in_schema=False)
def patch_config(body: ConfigPatch) -> dict:
    """Persist config key/value updates to SQLite and invalidate the in-process cache."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(settings.db_path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS runtime_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        for key, value in body.updates.items():
            conn.execute(
                "INSERT INTO runtime_config (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, value, now),
            )

    # Invalidate the in-process cache so next load_runtime_config() re-reads from DB
    _runtime_cache["ts"] = 0
    _runtime_cache["config"] = {}

    return {"updated": list(body.updates.keys())}


# ---------------------------------------------------------------------------
# POST /admin/retrain
# ---------------------------------------------------------------------------


def _ensure_retrain_jobs_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS retrain_jobs (
            job_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT
        )"""
    )


def _run_retrain(job_id: str) -> None:
    """Background task: run retraining and update job status in SQLite."""
    started_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(settings.db_path) as conn:
        _ensure_retrain_jobs_table(conn)
        conn.execute(
            "INSERT INTO retrain_jobs (job_id, status, started_at) VALUES (?, ?, ?)",
            (job_id, "running", started_at),
        )

    try:
        from detection.model_training import train_models
        from ingestion.synthetic_data import generate_synthetic_trades

        trades = generate_synthetic_trades()
        train_models(trades, model_dir=settings.model_dir)
        status = "completed"
    except Exception:
        status = "failed"

    completed_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(settings.db_path) as conn:
        _ensure_retrain_jobs_table(conn)
        conn.execute(
            "UPDATE retrain_jobs SET status=?, completed_at=? WHERE job_id=?",
            (status, completed_at, job_id),
        )


@router.post("/retrain", include_in_schema=False)
def trigger_retrain(background_tasks: BackgroundTasks) -> dict:
    """Enqueue an async retraining job and return its job ID."""
    job_id = str(uuid.uuid4())
    background_tasks.add_task(_run_retrain, job_id)
    return {"job_id": job_id, "status": "queued"}


# ---------------------------------------------------------------------------
# Soroban circuit breaker / DLQ endpoints  (Issue #143)
# ---------------------------------------------------------------------------

# Shared publisher singleton for the admin endpoints.
# In production the publisher is constructed by the pipeline; here we build
# a lightweight health-only instance backed by the same DB.
_soroban_publisher = None


def _get_publisher():
    """Return a shared SorobanPublisher instance (lazily constructed)."""
    global _soroban_publisher
    if _soroban_publisher is None:
        from detection.soroban_publisher import SorobanPublisher
        contract_id = os.environ.get("LEDGERLENS_SCORE_CONTRACT_ID", "")
        secret_key = os.environ.get("LEDGERLENS_SERVICE_SECRET_KEY", "")
        rpc_url = os.environ.get("SOROBAN_RPC_URL", "https://soroban-testnet.stellar.org")
        passphrase = os.environ.get("NETWORK_PASSPHRASE", "Test SDF Network ; September 2015")
        if not secret_key:
            # Return a stub that just exposes health from DB when key not configured
            from unittest.mock import MagicMock
            stub = MagicMock()
            stub.health.return_value = _build_health_from_db()
            return stub
        try:
            _soroban_publisher = SorobanPublisher(
                contract_id=contract_id,
                secret_key=secret_key,
                soroban_rpc_url=rpc_url,
                network_passphrase=passphrase,
            )
        except Exception:
            from unittest.mock import MagicMock
            stub = MagicMock()
            stub.health.return_value = _build_health_from_db()
            return stub
    return _soroban_publisher


def _build_health_from_db():
    """Build a minimal health dict from DB when no publisher is available."""
    from detection.soroban_publisher import get_dlq_pending_count, SorobanHealthStatus
    return SorobanHealthStatus(
        circuit_state="closed",
        consecutive_failures=0,
        last_error=None,
        circuit_opened_at=None,
        seconds_until_reset=None,
        dlq_pending_count=get_dlq_pending_count(),
    )


class SorobanHealthOut(BaseModel):
    circuit_state: str
    consecutive_failures: int
    last_error: Optional[str]
    circuit_opened_at: Optional[str]
    seconds_until_reset: Optional[float]
    dlq_pending_count: int


class DeadLetterItem(BaseModel):
    id: int
    wallet: str
    asset_pair: str
    score: int
    ledger_timestamp: int
    error_message: Optional[str]
    status: str
    created_at: str
    replayed_at: Optional[str]
    replay_tx_hash: Optional[str]


class PaginatedDeadLetters(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[DeadLetterItem]


def _health_to_out(h) -> SorobanHealthOut:
    return SorobanHealthOut(
        circuit_state=h.circuit_state,
        consecutive_failures=h.consecutive_failures,
        last_error=h.last_error,
        circuit_opened_at=h.circuit_opened_at.isoformat() if h.circuit_opened_at else None,
        seconds_until_reset=h.seconds_until_reset,
        dlq_pending_count=h.dlq_pending_count,
    )


@router.get("/soroban/health", response_model=SorobanHealthOut, include_in_schema=False)
def soroban_health() -> SorobanHealthOut:
    """Return the current Soroban circuit breaker state and DLQ pending count."""
    publisher = _get_publisher()
    return _health_to_out(publisher.health())


# POST /admin/soroban/reset is rate-limited to 10/minute
_reset_call_times: list[float] = []
_reset_lock = __import__("threading").Lock()
_RESET_RATE_LIMIT = 10
_RESET_RATE_WINDOW = 60.0


@router.post("/soroban/reset", response_model=SorobanHealthOut, include_in_schema=False)
def soroban_reset(request: Request) -> SorobanHealthOut:
    """Immediately close the Soroban circuit breaker (admin-only, rate-limited 10/min)."""
    now = time.monotonic()
    client_ip = request.client.host if request.client else "unknown"
    with _reset_lock:
        _reset_call_times[:] = [t for t in _reset_call_times if now - t < _RESET_RATE_WINDOW]
        if len(_reset_call_times) >= _RESET_RATE_LIMIT:
            raise HTTPException(status_code=429, detail="Reset rate limit exceeded (10/min)")
        _reset_call_times.append(now)
    logger.info("POST /admin/soroban/reset called from IP %s", client_ip)
    publisher = _get_publisher()
    return _health_to_out(publisher.reset_circuit())


@router.get("/soroban/dead-letters", response_model=PaginatedDeadLetters, include_in_schema=False)
def list_dead_letters(
    status: Optional[str] = Query(None, description="Filter by status: pending|replayed|failed"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> PaginatedDeadLetters:
    """Return paginated Soroban DLQ entries."""
    from detection.soroban_publisher import get_dlq_entries
    if status is not None and status not in ("pending", "replayed", "failed"):
        raise HTTPException(status_code=422, detail="status must be pending, replayed, or failed")
    items, total = get_dlq_entries(status=status, page=page, page_size=page_size)
    return PaginatedDeadLetters(
        total=total,
        page=page,
        page_size=page_size,
        items=[DeadLetterItem(**item) for item in items],
    )


import logging as _logging
logger = _logging.getLogger("ledgerlens.admin")
