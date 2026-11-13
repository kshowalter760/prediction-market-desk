
from dataclasses import dataclass
from decimal import Decimal

from prediction_desk.alignment import (
    calculate_aligned_spot_change,
)


@dataclass(frozen=True)
class CrossMarketAssessment:
    asset: str
    market_id: str
    previous_timestamp_ms: int
    current_timestamp_ms: int
    probability_change: Decimal
    spot_return: Decimal | None
    spot_change_usd: Decimal | None
    status: str
    explanation: str
    previous_candle_close_ms: int | None
    current_candle_close_ms: int | None


def assess_cross_market_event(
    asset,
    market_id,
    previous_timestamp_ms,
    current_timestamp_ms,
    probability_change,
    candles,
):
    if asset not in {"BTC", "ETH"}:
        raise ValueError("Unsupported asset")

    if not isinstance(market_id, str) or not market_id:
        raise ValueError("Invalid market ID")

    if (
        not isinstance(probability_change, Decimal)
        or not probability_change.is_finite()
        or abs(probability_change) > 1
    ):
        raise ValueError("Invalid probability change")

    if (
        not isinstance(previous_timestamp_ms, int)
        or isinstance(previous_timestamp_ms, bool)
        or not isinstance(current_timestamp_ms, int)
        or isinstance(current_timestamp_ms, bool)
        or previous_timestamp_ms <= 0
        or current_timestamp_ms <= previous_timestamp_ms
    ):
        raise ValueError("Invalid event window")

    candles = list(candles)

    if any(candle.asset != asset for candle in candles):
        raise ValueError("Candle asset mismatch")

    aligned = calculate_aligned_spot_change(
        candles=candles,
        previous_timestamp_ms=previous_timestamp_ms,
        current_timestamp_ms=current_timestamp_ms,
    )

    if aligned is None:
        return CrossMarketAssessment(
            asset=asset,
            market_id=market_id,
            previous_timestamp_ms=previous_timestamp_ms,
            current_timestamp_ms=current_timestamp_ms,
            probability_change=probability_change,
            spot_return=None,
            spot_change_usd=None,
            status="insufficient_spot_data",
            explanation=(
                "No eligible completed spot candle "
                "was available for both timestamps."
            ),
            previous_candle_close_ms=None,
            current_candle_close_ms=None,
        )

    previous_close = aligned.previous.candle_close_ms
    current_close = aligned.current.candle_close_ms

    if previous_close == current_close:
        status = "insufficient_time_resolution"
        explanation = (
            "Both timestamps map to the same completed "
            "one-minute candle. Sub-minute spot movement "
            "cannot be resolved."
        )
    else:
        status = "aligned_candle_comparison"
        explanation = (
            "Two distinct completed candles were used. "
            "The result describes candle-close movement, "
            "not necessarily the exact spot-price change "
            "during the Polymarket event."
        )

    return CrossMarketAssessment(
        asset=asset,
        market_id=market_id,
        previous_timestamp_ms=previous_timestamp_ms,
        current_timestamp_ms=current_timestamp_ms,
        probability_change=probability_change,
        spot_return=aligned.return_decimal,
        spot_change_usd=aligned.absolute_change_usd,
        status=status,
        explanation=explanation,
        previous_candle_close_ms=previous_close,
        current_candle_close_ms=current_close,
    )
