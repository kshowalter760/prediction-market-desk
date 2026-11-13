
from decimal import Decimal

import pytest

from prediction_desk.polymarket_stream import (
    MarketPriceChange,
    parse_market_message,
    parse_price_level_change,
)


def test_parse_complete_price_level_update():
    price, size, side = parse_price_level_change(
        {
            "price": "0.48",
            "size": "125.5",
            "side": "BUY",
        }
    )

    assert price == Decimal("0.48")
    assert size == Decimal("125.5")
    assert side == "BUY"


def test_zero_size_represents_level_removal():
    price, size, side = parse_price_level_change(
        {
            "price": "0.48",
            "size": "0",
            "side": "BUY",
        }
    )

    assert price == Decimal("0.48")
    assert size == Decimal("0")
    assert side == "BUY"


@pytest.mark.parametrize(
    "change",
    [
        {"price": "0.48", "size": "10"},
        {"price": "NaN", "size": "10", "side": "BUY"},
        {"price": "0.48", "size": "-1", "side": "BUY"},
        {"price": "0.48", "size": "10", "side": "INVALID"},
    ],
)
def test_invalid_level_updates_rejected(change):
    with pytest.raises(ValueError):
        parse_price_level_change(change)


def test_old_price_change_model_remains_compatible():
    event = MarketPriceChange(
        token_id="123",
        best_bid=Decimal("0.49"),
        best_ask=Decimal("0.50"),
        timestamp_ms=1000,
    )

    assert event.price is None
    assert event.size is None
    assert event.side is None


def test_price_change_parser_preserves_level_information():
    message = {
        "event_type": "price_change",
        "timestamp": "1793463267078",
        "price_changes": [
            {
                "asset_id": "123",
                "price": "0.48",
                "size": "100",
                "side": "BUY",
                "best_bid": "0.49",
                "best_ask": "0.50",
            }
        ],
    }

    events = parse_market_message(message)

    assert len(events) == 1
    assert events[0].price == Decimal("0.48")
    assert events[0].size == Decimal("100")
    assert events[0].side == "BUY"
    assert events[0].best_bid == Decimal("0.49")
