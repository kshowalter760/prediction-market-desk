
from decimal import Decimal

import pytest

from prediction_desk.spot import SpotTrade
from prediction_desk.spot_stream import (
    process_trade_messages,
)
from prediction_desk.stream_audit import (
    assess_stream_continuity,
)
from prediction_desk.storage import Storage


BASE = 1_800_000_000_000


def make_trade(asset, trade_id):
    return SpotTrade(
        asset=asset,
        trade_id=trade_id,
        timestamp_ms=BASE + trade_id,
        price_usd=Decimal("80000"),
        size=Decimal("0.01"),
    )


def message(trade_id):
    return {
        "type": "match",
        "product_id": "BTC-USD",
        "trade_id": trade_id,
        "time": "2026-10-27T01:00:00Z",
        "price": "80000",
        "size": "0.01",
    }


def test_separate_asset_continuity():
    trades = [
        make_trade("BTC", 101),
        make_trade("BTC", 102),
        make_trade("ETH", 501),
        make_trade("ETH", 502),
    ]

    result = assess_stream_continuity(trades)

    assert result.btc.status == "no_id_gaps_observed"
    assert result.eth.status == "no_id_gaps_observed"
    assert result.total_potential_gaps == 0


def test_detects_btc_gap():
    trades = [
        make_trade("BTC", 101),
        make_trade("BTC", 105),
        make_trade("ETH", 501),
        make_trade("ETH", 502),
    ]

    result = assess_stream_continuity(trades)

    assert result.total_potential_gaps == 1
    assert result.total_missing_ids == 3


def test_detects_gaps_in_both_assets():
    trades = [
        make_trade("BTC", 101),
        make_trade("BTC", 104),
        make_trade("ETH", 501),
        make_trade("ETH", 503),
    ]

    result = assess_stream_continuity(trades)

    assert result.total_potential_gaps == 2
    assert result.total_missing_ids == 3


def test_empty_stream():
    result = assess_stream_continuity([])

    assert result.btc.status == "no_data"
    assert result.eth.status == "no_data"


def test_rejects_unsupported_asset():
    with pytest.raises(ValueError):
        assess_stream_continuity([
            make_trade("SOL", 101),
        ])


def test_callback_captures_persisted_trades(tmp_path):
    received = []

    with Storage(tmp_path / "stream.db") as storage:
        storage.initialize()

        result = process_trade_messages(
            [
                message(101),
                message(103),
                message(103),
            ],
            storage,
            on_trade=received.append,
        )

        assert storage.count_spot_trades() == 2

    audit = assess_stream_continuity(received)

    assert result.trades_received == 3
    assert result.trades_inserted == 2
    assert len(received) == 3
    assert audit.btc.duplicate_ids == 1
    assert audit.total_potential_gaps == 1
    assert audit.total_missing_ids == 1
