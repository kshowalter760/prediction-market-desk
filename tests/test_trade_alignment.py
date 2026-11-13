
from decimal import Decimal

import pytest

from prediction_desk.spot import SpotTrade
from prediction_desk.trade_alignment import (
    align_spot_trade,
    calculate_trade_price_change,
)


BASE = 1_800_000_000_000


def make_trade(
    trade_id,
    offset_ms,
    price,
    asset="BTC",
):
    return SpotTrade(
        asset=asset,
        trade_id=trade_id,
        timestamp_ms=BASE + offset_ms,
        price_usd=Decimal(str(price)),
        size=Decimal("0.01"),
    )


def timestamp(offset_ms):
    return BASE + offset_ms


def test_uses_latest_eligible_trade():
    trades = [
        make_trade(1, 1000, "100"),
        make_trade(2, 3000, "105"),
        make_trade(3, 6000, "110"),
    ]

    result = align_spot_trade(
        trades,
        timestamp(4500),
    )

    assert result.trade_id == 2
    assert result.price_usd == Decimal("105")
    assert result.age_ms == 1500


def test_never_uses_future_trade():
    trades = [
        make_trade(1, 6000, "110"),
    ]

    result = align_spot_trade(
        trades,
        timestamp(4500),
    )

    assert result is None


def test_rejects_stale_trade():
    trades = [
        make_trade(1, 1000, "100"),
    ]

    result = align_spot_trade(
        trades,
        timestamp(9000),
    )

    assert result is None


def test_accepts_exact_timestamp():
    trades = [
        make_trade(1, 5000, "100"),
    ]

    result = align_spot_trade(
        trades,
        timestamp(5000),
    )

    assert result.age_ms == 0


def test_empty_trades_returns_none():
    assert align_spot_trade(
        [],
        timestamp(5000),
    ) is None


def test_rejects_mixed_assets():
    trades = [
        make_trade(1, 1000, "100", "BTC"),
        make_trade(2, 2000, "200", "ETH"),
    ]

    with pytest.raises(ValueError):
        align_spot_trade(
            trades,
            timestamp(3000),
        )


def test_calculates_subminute_return():
    trades = [
        make_trade(1, 1000, "100"),
        make_trade(2, 12000, "101"),
        make_trade(3, 22000, "102"),
    ]

    result = calculate_trade_price_change(
        trades,
        previous_timestamp_ms=timestamp(3000),
        current_timestamp_ms=timestamp(24000),
    )

    assert result.status == "distinct_trades"
    assert result.absolute_change_usd == Decimal("2")
    assert result.return_decimal == Decimal("0.02")


def test_same_trade_is_identified():
    trades = [
        make_trade(1, 1000, "100"),
    ]

    result = calculate_trade_price_change(
        trades,
        previous_timestamp_ms=timestamp(2000),
        current_timestamp_ms=timestamp(3000),
    )

    assert result.status == "same_trade"
    assert result.return_decimal == Decimal("0")


def test_missing_endpoint_returns_none():
    trades = [
        make_trade(1, 1000, "100"),
    ]

    result = calculate_trade_price_change(
        trades,
        previous_timestamp_ms=timestamp(2000),
        current_timestamp_ms=timestamp(20000),
    )

    assert result is None


def test_rejects_reverse_window():
    with pytest.raises(ValueError):
        calculate_trade_price_change(
            [],
            previous_timestamp_ms=timestamp(20000),
            current_timestamp_ms=timestamp(10000),
        )
