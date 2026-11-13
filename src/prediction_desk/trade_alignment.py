
from dataclasses import dataclass
from decimal import Decimal

from prediction_desk.spot import SpotTrade


@dataclass(frozen=True)
class AlignedSpotTrade:
    asset: str
    event_timestamp_ms: int
    trade_id: int
    trade_timestamp_ms: int
    price_usd: Decimal
    age_ms: int


@dataclass(frozen=True)
class TradePriceChange:
    asset: str
    previous: AlignedSpotTrade
    current: AlignedSpotTrade
    absolute_change_usd: Decimal
    return_decimal: Decimal
    status: str


def align_spot_trade(
    trades,
    event_timestamp_ms,
    max_age_ms=5000,
):
    if (
        not isinstance(event_timestamp_ms, int)
        or isinstance(event_timestamp_ms, bool)
        or event_timestamp_ms <= 0
    ):
        raise ValueError("Invalid event timestamp")

    if (
        not isinstance(max_age_ms, int)
        or isinstance(max_age_ms, bool)
        or max_age_ms < 0
    ):
        raise ValueError("Invalid maximum age")

    trades = list(trades)

    if not all(
        isinstance(trade, SpotTrade)
        for trade in trades
    ):
        raise TypeError("Expected SpotTrade objects")

    if not trades:
        return None

    if len({trade.asset for trade in trades}) != 1:
        raise ValueError("Mixed assets are not allowed")

    eligible = [
        trade
        for trade in trades
        if (
            trade.timestamp_ms <= event_timestamp_ms
            and event_timestamp_ms - trade.timestamp_ms
            <= max_age_ms
        )
    ]

    if not eligible:
        return None

    latest = max(
        eligible,
        key=lambda trade: (
            trade.timestamp_ms,
            trade.trade_id,
        ),
    )

    return AlignedSpotTrade(
        asset=latest.asset,
        event_timestamp_ms=event_timestamp_ms,
        trade_id=latest.trade_id,
        trade_timestamp_ms=latest.timestamp_ms,
        price_usd=latest.price_usd,
        age_ms=(
            event_timestamp_ms - latest.timestamp_ms
        ),
    )


def calculate_trade_price_change(
    trades,
    previous_timestamp_ms,
    current_timestamp_ms,
    max_age_ms=5000,
):
    if (
        not isinstance(previous_timestamp_ms, int)
        or isinstance(previous_timestamp_ms, bool)
        or previous_timestamp_ms <= 0
        or not isinstance(current_timestamp_ms, int)
        or isinstance(current_timestamp_ms, bool)
        or current_timestamp_ms <= previous_timestamp_ms
    ):
        raise ValueError("Invalid event window")

    previous = align_spot_trade(
        trades,
        previous_timestamp_ms,
        max_age_ms,
    )

    current = align_spot_trade(
        trades,
        current_timestamp_ms,
        max_age_ms,
    )

    if previous is None or current is None:
        return None

    if previous.asset != current.asset:
        raise ValueError("Spot asset mismatch")

    absolute_change = (
        current.price_usd - previous.price_usd
    )

    if previous.trade_id == current.trade_id:
        status = "same_trade"
    else:
        status = "distinct_trades"

    return TradePriceChange(
        asset=current.asset,
        previous=previous,
        current=current,
        absolute_change_usd=absolute_change,
        return_decimal=(
            absolute_change / previous.price_usd
        ),
        status=status,
    )
