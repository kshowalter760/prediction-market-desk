
from decimal import Decimal

import pytest

from prediction_desk.cross_market import (
    assess_cross_market_event,
)
from prediction_desk.spot import SpotCandle


BASE = 1_800_000_000


def make_candle(offset, price, asset="BTC"):
    value = Decimal(str(price))

    return SpotCandle(
        asset=asset,
        start_timestamp_s=BASE + offset,
        open_usd=value,
        high_usd=value,
        low_usd=value,
        close_usd=value,
        volume=Decimal("10"),
    )


def timestamp_ms(offset):
    return (BASE + offset) * 1000


def assess(candles, previous=65, current=125):
    return assess_cross_market_event(
        asset="BTC",
        market_id="100",
        previous_timestamp_ms=timestamp_ms(previous),
        current_timestamp_ms=timestamp_ms(current),
        probability_change=Decimal("-0.23"),
        candles=candles,
    )


def test_distinct_candles_produce_comparison():
    result = assess([
        make_candle(0, "100"),
        make_candle(60, "110"),
    ])

    assert result.status == "aligned_candle_comparison"
    assert result.spot_return == Decimal("0.1")
    assert result.spot_change_usd == Decimal("10")


def test_same_candle_is_inconclusive():
    result = assess(
        [make_candle(0, "100")],
        previous=65,
        current=85,
    )

    assert result.status == "insufficient_time_resolution"
    assert result.spot_return == Decimal("0")


def test_missing_candles_are_inconclusive():
    result = assess([])

    assert result.status == "insufficient_spot_data"
    assert result.spot_return is None


def test_wrong_asset_is_rejected():
    with pytest.raises(ValueError):
        assess([make_candle(0, "100", "ETH")])


def test_invalid_probability_change():
    with pytest.raises(ValueError):
        assess_cross_market_event(
            asset="BTC",
            market_id="100",
            previous_timestamp_ms=timestamp_ms(65),
            current_timestamp_ms=timestamp_ms(125),
            probability_change=Decimal("1.5"),
            candles=[],
        )


def test_rejects_reverse_window():
    with pytest.raises(ValueError):
        assess(
            [],
            previous=125,
            current=65,
        )
