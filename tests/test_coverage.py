
from decimal import Decimal

import pytest

from prediction_desk.coverage import (
    assess_trade_coverage,
)
from prediction_desk.spot import SpotTrade


BASE = 1_800_000_000_000


def make_trade(trade_id, offset_ms, asset="BTC"):
    return SpotTrade(
        asset=asset,
        trade_id=trade_id,
        timestamp_ms=BASE + offset_ms,
        price_usd=Decimal("80000"),
        size=Decimal("0.01"),
    )


def test_empty_coverage():
    result = assess_trade_coverage([], "BTC")

    assert result.status == "no_data"
    assert result.trade_count == 0


def test_single_trade():
    result = assess_trade_coverage(
        [make_trade(1, 1000)],
        "BTC",
    )

    assert result.status == "insufficient_samples"


def test_detects_large_timestamp_gap():
    trades = [
        make_trade(1, 1000),
        make_trade(2, 2000),
        make_trade(3, 12000),
    ]

    result = assess_trade_coverage(
        trades,
        "BTC",
        max_gap_seconds=5,
    )

    assert result.status == "observed_time_gap"
    assert result.largest_gap_seconds == 10.0


def test_no_large_observed_gap():
    trades = [
        make_trade(1, 1000),
        make_trade(2, 2000),
        make_trade(3, 3000),
    ]

    result = assess_trade_coverage(trades, "BTC")

    assert result.status == "no_large_observed_gap"
    assert result.span_seconds == 2.0


def test_rejects_mixed_assets():
    trades = [
        make_trade(1, 1000, "BTC"),
        make_trade(2, 2000, "ETH"),
    ]

    with pytest.raises(ValueError):
        assess_trade_coverage(trades, "BTC")


def test_rejects_invalid_gap():
    with pytest.raises(ValueError):
        assess_trade_coverage(
            [],
            "BTC",
            max_gap_seconds=-1,
        )
