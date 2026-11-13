
from decimal import Decimal

import pytest

from prediction_desk.alignment import (
    align_completed_candle,
    calculate_aligned_spot_change,
)
from prediction_desk.spot import SpotCandle


BASE = 1_800_000_000


def make_candle(offset_seconds, close_price, asset="BTC"):
    price = Decimal(str(close_price))

    return SpotCandle(
        asset=asset,
        start_timestamp_s=BASE + offset_seconds,
        open_usd=price,
        high_usd=price,
        low_usd=price,
        close_usd=price,
        volume=Decimal("10"),
    )


def event_ms(offset_seconds):
    return (BASE + offset_seconds) * 1000


def test_uses_latest_completed_candle():
    candles = [
        make_candle(0, "100"),
        make_candle(60, "110"),
        make_candle(120, "120"),
    ]

    result = align_completed_candle(
        candles,
        event_ms(150),
    )

    assert result.price_usd == Decimal("110")
    assert result.age_ms == 30000


def test_rejects_unfinished_candle():
    candles = [make_candle(60, "110")]

    result = align_completed_candle(
        candles,
        event_ms(90),
    )

    assert result is None


def test_rejects_stale_candle():
    candles = [make_candle(0, "100")]

    result = align_completed_candle(
        candles,
        event_ms(300),
    )

    assert result is None


def test_accepts_exact_completion_time():
    candles = [make_candle(0, "100")]

    result = align_completed_candle(
        candles,
        event_ms(60),
    )

    assert result.price_usd == Decimal("100")
    assert result.age_ms == 0


def test_empty_history_returns_none():
    assert align_completed_candle(
        [],
        event_ms(120),
    ) is None


def test_rejects_mixed_assets():
    candles = [
        make_candle(0, "100", "BTC"),
        make_candle(60, "200", "ETH"),
    ]

    with pytest.raises(ValueError):
        align_completed_candle(
            candles,
            event_ms(180),
        )


def test_calculates_spot_return():
    candles = [
        make_candle(0, "100"),
        make_candle(60, "110"),
    ]

    result = calculate_aligned_spot_change(
        candles,
        previous_timestamp_ms=event_ms(65),
        current_timestamp_ms=event_ms(125),
    )

    assert result.absolute_change_usd == Decimal("10")
    assert result.return_decimal == Decimal("0.1")


def test_rejects_reverse_event_window():
    with pytest.raises(ValueError):
        calculate_aligned_spot_change(
            [],
            previous_timestamp_ms=event_ms(120),
            current_timestamp_ms=event_ms(60),
        )
