
from dataclasses import dataclass


@dataclass(frozen=True)
class TradeCoverage:
    asset: str
    trade_count: int
    first_timestamp_ms: int | None
    last_timestamp_ms: int | None
    span_seconds: float
    largest_gap_seconds: float
    status: str


def assess_trade_coverage(
    trades,
    asset,
    max_gap_seconds=5,
):
    if asset not in {"BTC", "ETH"}:
        raise ValueError("Unsupported asset")

    if (
        isinstance(max_gap_seconds, bool)
        or not isinstance(max_gap_seconds, (int, float))
        or not 0 < max_gap_seconds < float("inf")
    ):
        raise ValueError("Invalid maximum gap")

    trades = list(trades)

    if not trades:
        return TradeCoverage(
            asset=asset,
            trade_count=0,
            first_timestamp_ms=None,
            last_timestamp_ms=None,
            span_seconds=0.0,
            largest_gap_seconds=0.0,
            status="no_data",
        )

    if any(trade.asset != asset for trade in trades):
        raise ValueError("Trade asset mismatch")

    timestamps = sorted(
        trade.timestamp_ms
        for trade in trades
    )

    if any(
        not isinstance(timestamp, int)
        or isinstance(timestamp, bool)
        or timestamp <= 0
        for timestamp in timestamps
    ):
        raise ValueError("Invalid trade timestamp")

    gaps_ms = [
        current - previous
        for previous, current in zip(
            timestamps,
            timestamps[1:],
        )
    ]

    largest_gap_ms = max(gaps_ms, default=0)

    span_seconds = (
        timestamps[-1] - timestamps[0]
    ) / 1000

    largest_gap_seconds = largest_gap_ms / 1000

    if len(trades) < 2:
        status = "insufficient_samples"
    elif largest_gap_seconds > max_gap_seconds:
        status = "observed_time_gap"
    else:
        status = "no_large_observed_gap"

    return TradeCoverage(
        asset=asset,
        trade_count=len(trades),
        first_timestamp_ms=timestamps[0],
        last_timestamp_ms=timestamps[-1],
        span_seconds=span_seconds,
        largest_gap_seconds=largest_gap_seconds,
        status=status,
    )
