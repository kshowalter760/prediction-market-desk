
from decimal import Decimal

import pytest

from prediction_desk.continuity import (
    assess_trade_continuity,
)
from prediction_desk.spot import SpotTrade


BASE = 1_800_000_000_000


def make_trade(trade_id, asset="BTC"):
    return SpotTrade(
        asset=asset,
        trade_id=trade_id,
        timestamp_ms=BASE + trade_id,
        price_usd=Decimal("80000"),
        size=Decimal("0.01"),
    )


def test_consecutive_trade_ids():
    trades = [
        make_trade(101),
        make_trade(102),
        make_trade(103),
    ]

    report = assess_trade_continuity(
        trades,
        "BTC",
    )

    assert report.status == "no_id_gaps_observed"
    assert report.gaps == ()


def test_detects_missing_ids():
    trades = [
        make_trade(101),
        make_trade(105),
    ]

    report = assess_trade_continuity(
        trades,
        "BTC",
    )

    assert report.status == "potential_gaps"
    assert len(report.gaps) == 1
    assert report.gaps[0].missing_id_count == 3


def test_out_of_order_trades():
    trades = [
        make_trade(103),
        make_trade(101),
        make_trade(102),
    ]

    report = assess_trade_continuity(
        trades,
        "BTC",
    )

    assert report.status == "no_id_gaps_observed"


def test_duplicate_ids():
    trades = [
        make_trade(101),
        make_trade(101),
        make_trade(102),
    ]

    report = assess_trade_continuity(
        trades,
        "BTC",
    )

    assert report.duplicate_ids == 1
    assert report.unique_trades == 2


def test_single_trade():
    report = assess_trade_continuity(
        [make_trade(101)],
        "BTC",
    )

    assert report.status == "insufficient_samples"


def test_empty_trades():
    report = assess_trade_continuity(
        [],
        "BTC",
    )

    assert report.status == "no_data"


def test_rejects_mixed_assets():
    trades = [
        make_trade(101, "BTC"),
        make_trade(102, "ETH"),
    ]

    with pytest.raises(ValueError):
        assess_trade_continuity(
            trades,
            "BTC",
        )


def test_rejects_invalid_asset():
    with pytest.raises(ValueError):
        assess_trade_continuity(
            [],
            "SOL",
        )
