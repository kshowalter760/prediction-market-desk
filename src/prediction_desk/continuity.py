
from dataclasses import dataclass

from prediction_desk.spot import SpotTrade


@dataclass(frozen=True)
class TradeGap:
    asset: str
    previous_trade_id: int
    current_trade_id: int
    missing_id_count: int


@dataclass(frozen=True)
class ContinuityReport:
    asset: str
    trades_examined: int
    unique_trades: int
    duplicate_ids: int
    gaps: tuple[TradeGap, ...]
    status: str


def assess_trade_continuity(trades, asset):
    if asset not in {"BTC", "ETH"}:
        raise ValueError("Unsupported asset")

    trades = list(trades)

    if not all(
        isinstance(trade, SpotTrade)
        for trade in trades
    ):
        raise TypeError("Expected SpotTrade objects")

    if any(trade.asset != asset for trade in trades):
        raise ValueError("Trade asset mismatch")

    trade_ids = [
        trade.trade_id
        for trade in trades
    ]

    if any(
        not isinstance(trade_id, int)
        or isinstance(trade_id, bool)
        or trade_id <= 0
        for trade_id in trade_ids
    ):
        raise ValueError("Invalid trade ID")

    unique_ids = sorted(set(trade_ids))

    duplicate_count = (
        len(trade_ids) - len(unique_ids)
    )

    gaps = []

    for previous, current in zip(
        unique_ids,
        unique_ids[1:],
    ):
        missing_count = current - previous - 1

        if missing_count > 0:
            gaps.append(
                TradeGap(
                    asset=asset,
                    previous_trade_id=previous,
                    current_trade_id=current,
                    missing_id_count=missing_count,
                )
            )

    if not unique_ids:
        status = "no_data"
    elif len(unique_ids) == 1:
        status = "insufficient_samples"
    elif gaps:
        status = "potential_gaps"
    else:
        status = "no_id_gaps_observed"

    return ContinuityReport(
        asset=asset,
        trades_examined=len(trades),
        unique_trades=len(unique_ids),
        duplicate_ids=duplicate_count,
        gaps=tuple(gaps),
        status=status,
    )
