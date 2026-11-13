
import json
from decimal import Decimal

import pytest

from prediction_desk.polymarket_stream import (
    MarketBookEvent,
    MarketPriceChange,
    build_market_subscription,
    parse_market_message,
)


def test_subscription():
    result = build_market_subscription(
        ["token_yes", "token_no"]
    )

    assert result["type"] == "market"
    assert result["assets_ids"] == [
        "token_yes",
        "token_no",
    ]


def test_rejects_empty_subscription():
    with pytest.raises(ValueError):
        build_market_subscription([])


def test_parses_book():
    message = {
        "event_type": "book",
        "asset_id": "token_yes",
        "timestamp": "1790000000000",
        "hash": "abc123",
        "bids": [
            {"price": "0.45", "size": "100"}
        ],
        "asks": [
            {"price": "0.47", "size": "80"}
        ],
    }

    events = parse_market_message(
        json.dumps(message)
    )

    assert len(events) == 1
    assert isinstance(events[0], MarketBookEvent)
    assert events[0].token_id == "token_yes"
    assert events[0].bids[0][0] == Decimal("0.45")


def test_parses_price_change():
    message = {
        "event_type": "price_change",
        "price_changes": [
            {
                "asset_id": "token_yes",
                "best_bid": "0.51",
                "best_ask": "0.53",
            }
        ],
    }

    events = parse_market_message(message)

    assert len(events) == 1
    assert isinstance(
        events[0],
        MarketPriceChange,
    )
    assert events[0].best_bid == Decimal("0.51")


def test_parses_batch():
    book = {
        "event_type": "book",
        "asset_id": "token_yes",
        "timestamp": "1790000000000",
        "bids": [],
        "asks": [],
    }

    events = parse_market_message(
        [book, book]
    )

    assert len(events) == 2


def test_ignores_pong():
    assert parse_market_message("PONG") == []


def test_rejects_invalid_price():
    message = {
        "event_type": "book",
        "asset_id": "token_yes",
        "timestamp": "1790000000000",
        "bids": [
            {"price": "1.5", "size": "100"}
        ],
        "asks": [],
    }

    with pytest.raises(ValueError):
        parse_market_message(message)


def test_price_change_preserves_source_timestamp():
    message = {
        "event_type": "price_change",
        "timestamp": "1793140000123",
        "price_changes": [
            {
                "asset_id": "123456",
                "best_bid": "0.50",
                "best_ask": "0.51",
            },
            {
                "asset_id": "789012",
                "best_bid": "0.49",
                "best_ask": "0.50",
            },
        ],
    }

    events = parse_market_message(message)

    assert len(events) == 2
    assert events[0].timestamp_ms == 1793140000123
    assert events[1].timestamp_ms == 1793140000123


def test_price_change_without_timestamp_remains_supported():
    message = {
        "event_type": "price_change",
        "price_changes": [
            {
                "asset_id": "123456",
                "best_bid": "0.50",
                "best_ask": "0.51",
            }
        ],
    }

    events = parse_market_message(message)

    assert len(events) == 1
    assert events[0].timestamp_ms is None


def test_price_change_rejects_invalid_timestamp():
    message = {
        "event_type": "price_change",
        "timestamp": "-100",
        "price_changes": [
            {
                "asset_id": "123456",
                "best_bid": "0.50",
                "best_ask": "0.51",
            }
        ],
    }

    with pytest.raises(ValueError, match="timestamp"):
        parse_market_message(message)

