
import json

import pytest

from prediction_desk.spot_stream import (
    build_subscription,
    parse_trade_message,
    process_trade_messages,
)
from prediction_desk.storage import Storage


def trade_message(
    trade_id=101,
    product_id="BTC-USD",
):
    return {
        "type": "match",
        "product_id": product_id,
        "trade_id": trade_id,
        "time": "2026-10-27T01:00:00.123456Z",
        "price": "80000.50",
        "size": "0.01",
    }


def test_subscription_includes_both_assets():
    subscription = build_subscription()

    assert subscription["type"] == "subscribe"
    assert set(subscription["product_ids"]) == {
        "BTC-USD",
        "ETH-USD",
    }
    assert subscription["channels"] == ["matches"]


def test_parses_btc_trade():
    trade = parse_trade_message(trade_message())

    assert trade.asset == "BTC"
    assert trade.trade_id == 101
    assert str(trade.price_usd) == "80000.50"


def test_parses_eth_trade():
    trade = parse_trade_message(
        trade_message(product_id="ETH-USD")
    )

    assert trade.asset == "ETH"


def test_ignores_non_trade_messages():
    assert parse_trade_message({
        "type": "subscriptions"
    }) is None


def test_stream_persists_and_deduplicates(tmp_path):
    messages = [
        json.dumps(trade_message(101)),
        json.dumps(trade_message(101)),
        json.dumps(trade_message(102)),
    ]

    with Storage(tmp_path / "stream.db") as storage:
        storage.initialize()

        result = process_trade_messages(
            messages,
            storage,
        )

        assert storage.count_spot_trades() == 2

    assert result.messages_received == 3
    assert result.trades_received == 3
    assert result.trades_inserted == 2


def test_rejects_invalid_stream_limit(tmp_path):
    with Storage(tmp_path / "stream.db") as storage:
        storage.initialize()

        with pytest.raises(ValueError):
            process_trade_messages(
                [],
                storage,
                max_messages=0,
            )
