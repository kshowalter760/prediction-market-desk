
from dataclasses import dataclass
from datetime import datetime, timezone

from prediction_desk.spot import SpotAPIError


@dataclass(frozen=True)
class SpotCollectionResult:
    asset: str
    fetched: int
    inserted: int
    duplicate_count: int
    first_trade_timestamp_ms: int | None
    last_trade_timestamp_ms: int | None
    coverage_seconds: float
    status: str


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def collect_spot_trades(
    client,
    storage,
    assets=("BTC", "ETH"),
    limit=100,
):
    if not isinstance(assets, (list, tuple)):
        raise ValueError("Assets must be a list or tuple")

    if not assets:
        raise ValueError("At least one asset is required")

    if len(assets) != len(set(assets)):
        raise ValueError("Duplicate assets are not allowed")

    if any(asset not in {"BTC", "ETH"} for asset in assets):
        raise ValueError("Unsupported asset")

    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= 100
    ):
        raise ValueError("Invalid trade limit")

    results = []

    for asset in assets:
        started_at_utc = utc_now()

        try:
            trades = client.get_recent_trades(
                asset,
                limit=limit,
            )

        except SpotAPIError:
            completed_at_utc = utc_now()

            storage.save_spot_collection_run(
                asset=asset,
                started_at_utc=started_at_utc,
                completed_at_utc=completed_at_utc,
                status="api_error",
                fetched=0,
                inserted=0,
            )

            results.append(
                SpotCollectionResult(
                    asset=asset,
                    fetched=0,
                    inserted=0,
                    duplicate_count=0,
                    first_trade_timestamp_ms=None,
                    last_trade_timestamp_ms=None,
                    coverage_seconds=0.0,
                    status="api_error",
                )
            )
            continue

        completed_at_utc = utc_now()

        if not trades:
            storage.save_spot_collection_run(
                asset=asset,
                started_at_utc=started_at_utc,
                completed_at_utc=completed_at_utc,
                status="empty_response",
                fetched=0,
                inserted=0,
            )

            results.append(
                SpotCollectionResult(
                    asset=asset,
                    fetched=0,
                    inserted=0,
                    duplicate_count=0,
                    first_trade_timestamp_ms=None,
                    last_trade_timestamp_ms=None,
                    coverage_seconds=0.0,
                    status="empty_response",
                )
            )
            continue

        inserted = storage.save_spot_trades(trades)

        duplicate_count = len(trades) - inserted

        first_timestamp = min(
            trade.timestamp_ms
            for trade in trades
        )

        last_timestamp = max(
            trade.timestamp_ms
            for trade in trades
        )

        first_trade_id = min(
            trade.trade_id
            for trade in trades
        )

        last_trade_id = max(
            trade.trade_id
            for trade in trades
        )

        coverage_seconds = (
            last_timestamp - first_timestamp
        ) / 1000

        storage.save_spot_collection_run(
            asset=asset,
            started_at_utc=started_at_utc,
            completed_at_utc=completed_at_utc,
            status="success",
            fetched=len(trades),
            inserted=inserted,
            first_trade_id=first_trade_id,
            last_trade_id=last_trade_id,
            first_trade_timestamp_ms=first_timestamp,
            last_trade_timestamp_ms=last_timestamp,
            overlap_count=duplicate_count,
        )

        results.append(
            SpotCollectionResult(
                asset=asset,
                fetched=len(trades),
                inserted=inserted,
                duplicate_count=duplicate_count,
                first_trade_timestamp_ms=first_timestamp,
                last_trade_timestamp_ms=last_timestamp,
                coverage_seconds=coverage_seconds,
                status="success",
            )
        )

    return results


def format_timestamp(timestamp_ms):
    if timestamp_ms is None:
        return "N/A"

    return datetime.fromtimestamp(
        timestamp_ms / 1000,
        tz=timezone.utc,
    ).isoformat()
