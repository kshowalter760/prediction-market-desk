
from dataclasses import dataclass
from decimal import Decimal

from prediction_desk.spot import SpotCandle


CANDLE_DURATION_MS = 60_000


@dataclass(frozen=True)
class AlignedSpotPrice:
    asset: str
    event_timestamp_ms: int
    candle_start_ms: int
    candle_close_ms: int
    price_usd: Decimal
    age_ms: int


@dataclass(frozen=True)
class SpotPriceChange:
    asset: str
    previous: AlignedSpotPrice
    current: AlignedSpotPrice
    absolute_change_usd: Decimal
    return_decimal: Decimal


def align_completed_candle(
    candles,
    event_timestamp_ms,
    max_age_seconds=120,
):
    if (
        not isinstance(event_timestamp_ms, int)
        or isinstance(event_timestamp_ms, bool)
        or event_timestamp_ms <= 0
    ):
        raise ValueError("Invalid event timestamp")

    if (
        not isinstance(max_age_seconds, int)
        or isinstance(max_age_seconds, bool)
        or max_age_seconds < 0
    ):
        raise ValueError("Invalid maximum age")

    candles = list(candles)

    if not all(
        isinstance(candle, SpotCandle)
        for candle in candles
    ):
        raise TypeError("Expected SpotCandle objects")

    if not candles:
        return None

    assets = {candle.asset for candle in candles}

    if len(assets) != 1:
        raise ValueError("Mixed assets are not allowed")

    eligible = []

    for candle in candles:
        candle_start_ms = (
            candle.start_timestamp_s * 1000
        )
        candle_close_ms = (
            candle_start_ms + CANDLE_DURATION_MS
        )

        if candle_close_ms > event_timestamp_ms:
            continue

        age_ms = event_timestamp_ms - candle_close_ms

        if age_ms > max_age_seconds * 1000:
            continue

        eligible.append(
            (candle_close_ms, candle, age_ms)
        )

    if not eligible:
        return None

    close_ms, candle, age_ms = max(
        eligible,
        key=lambda item: item[0],
    )

    return AlignedSpotPrice(
        asset=candle.asset,
        event_timestamp_ms=event_timestamp_ms,
        candle_start_ms=(
            candle.start_timestamp_s * 1000
        ),
        candle_close_ms=close_ms,
        price_usd=candle.close_usd,
        age_ms=age_ms,
    )


def calculate_aligned_spot_change(
    candles,
    previous_timestamp_ms,
    current_timestamp_ms,
    max_age_seconds=120,
):
    if (
        not isinstance(previous_timestamp_ms, int)
        or isinstance(previous_timestamp_ms, bool)
        or not isinstance(current_timestamp_ms, int)
        or isinstance(current_timestamp_ms, bool)
        or previous_timestamp_ms <= 0
        or current_timestamp_ms <= previous_timestamp_ms
    ):
        raise ValueError("Invalid event time window")

    previous = align_completed_candle(
        candles,
        previous_timestamp_ms,
        max_age_seconds,
    )

    current = align_completed_candle(
        candles,
        current_timestamp_ms,
        max_age_seconds,
    )

    if previous is None or current is None:
        return None

    if previous.asset != current.asset:
        raise ValueError("Spot asset mismatch")

    absolute_change = (
        current.price_usd - previous.price_usd
    )

    return SpotPriceChange(
        asset=current.asset,
        previous=previous,
        current=current,
        absolute_change_usd=absolute_change,
        return_decimal=(
            absolute_change / previous.price_usd
        ),
    )
