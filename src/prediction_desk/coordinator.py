
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic
from typing import Callable

from prediction_desk.polymarket_live import (
    collect_live_market,
)
from prediction_desk.storage import Storage
from prediction_desk.stream_supervisor import (
    run_supervised_stream,
)


@dataclass(frozen=True)
class WorkerOutcome:
    name: str
    status: str
    result: object | None
    error: str | None


@dataclass(frozen=True)
class CoordinatedSessionResult:
    started_at_utc: str
    completed_at_utc: str
    duration_seconds: float
    coinbase: WorkerOutcome
    polymarket: WorkerOutcome


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def validate_token_ids(token_ids):
    tokens = list(token_ids)

    if not tokens or any(
        not isinstance(token, str)
        or not token.isascii()
        or not token.isdecimal()
        for token in tokens
    ):
        raise ValueError(
            "Token IDs must be nonempty ASCII decimal strings"
        )

    if len(tokens) != len(set(tokens)):
        raise ValueError("Duplicate token IDs")

    return tokens


def run_worker(name: str, operation: Callable):
    try:
        result = operation()

        return WorkerOutcome(
            name=name,
            status="completed",
            result=result,
            error=None,
        )

    except Exception as exc:
        return WorkerOutcome(
            name=name,
            status="failed",
            result=None,
            error=f"{type(exc).__name__}: {exc}",
        )


def run_coordinated_session(
    database_path,
    token_ids,
    duration_seconds=30,
    coinbase_max_messages=100000,
    polymarket_max_messages=100000,
    coinbase_collector=run_supervised_stream,
    polymarket_collector=collect_live_market,
):
    tokens = validate_token_ids(token_ids)

    if (
        isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, (int, float))
        or not 0 < duration_seconds < float("inf")
    ):
        raise ValueError("Invalid session duration")

    database_path = str(database_path)

    # Initialize schema before concurrent collection.
    with Storage(database_path) as storage:
        storage.initialize()

    started_at = utc_now()
    start = monotonic()

    def collect_coinbase():
        # Independent SQLite connection for Coinbase.
        with Storage(database_path) as storage:
            return coinbase_collector(
                storage=storage,
                max_messages=coinbase_max_messages,
                duration_seconds=duration_seconds,
            )

    def collect_polymarket():
        # Independent SQLite connection for Polymarket.
        with Storage(database_path) as storage:
            return polymarket_collector(
                token_ids=tokens,
                duration_seconds=duration_seconds,
                max_messages=polymarket_max_messages,
                storage=storage,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        coinbase_future = executor.submit(
            run_worker,
            "coinbase",
            collect_coinbase,
        )

        polymarket_future = executor.submit(
            run_worker,
            "polymarket",
            collect_polymarket,
        )

        coinbase = coinbase_future.result()
        polymarket = polymarket_future.result()

    return CoordinatedSessionResult(
        started_at_utc=started_at,
        completed_at_utc=utc_now(),
        duration_seconds=monotonic() - start,
        coinbase=coinbase,
        polymarket=polymarket,
    )
