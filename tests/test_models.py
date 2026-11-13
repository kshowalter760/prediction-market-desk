
from decimal import Decimal

import pytest

from prediction_desk.models import (
    OrderBook,
    OrderBookLevel,
)


def test_valid_order_book_level():
    level = OrderBookLevel.from_api({
        "price": "0.028",
        "size": "10874.82",
    })

    assert level.price == Decimal("0.028")
    assert level.size == Decimal("10874.82")


def test_invalid_price():
    with pytest.raises(ValueError):
        OrderBookLevel.from_api({
            "price": "1.5",
            "size": "100",
        })


def test_invalid_size():
    with pytest.raises(ValueError):
        OrderBookLevel.from_api({
            "price": "0.5",
            "size": "-10",
        })


def test_best_prices_and_spread():
    book = OrderBook.from_api({
        "asset_id": "123456",
        "bids": [
            {"price": "0.01", "size": "100"},
            {"price": "0.028", "size": "50"},
        ],
        "asks": [
            {"price": "0.999", "size": "100"},
            {"price": "0.029", "size": "50"},
        ],
    })

    assert book.best_bid == Decimal("0.028")
    assert book.best_ask == Decimal("0.029")
    assert book.spread == Decimal("0.001")


def test_empty_order_book():
    book = OrderBook.from_api({
        "asset_id": "123456",
        "bids": [],
        "asks": [],
    })

    assert book.best_bid is None
    assert book.best_ask is None
    assert book.spread is None
