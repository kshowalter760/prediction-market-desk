
from decimal import Decimal

import pytest

from prediction_desk.book_depth import parse_book_depth


def test_parse_full_book():
    message = {
        "bids": [
            {"price": "0.45", "size": "100"},
            {"price": "0.44", "size": "200"},
        ],
        "asks": [
            {"price": "0.55", "size": "150"},
        ],
    }

    levels = parse_book_depth(message)

    assert len(levels) == 3
    assert levels[0].side == "BUY"
    assert levels[0].price == Decimal("0.45")
    assert levels[1].size == Decimal("200")
    assert levels[2].side == "SELL"


def test_empty_book_is_valid():
    levels = parse_book_depth({
        "bids": [],
        "asks": [],
    })

    assert levels == []


def test_missing_asks_rejected():
    with pytest.raises(ValueError, match="asks"):
        parse_book_depth({
            "bids": [],
        })


def test_negative_size_rejected():
    with pytest.raises(ValueError, match="nonnegative"):
        parse_book_depth({
            "bids": [
                {"price": "0.45", "size": "-1"},
            ],
            "asks": [],
        })


def test_invalid_price_rejected():
    with pytest.raises(ValueError, match="price"):
        parse_book_depth({
            "bids": [
                {"price": "1.5", "size": "100"},
            ],
            "asks": [],
        })


def test_nonfinite_size_rejected():
    with pytest.raises(ValueError, match="nonnegative"):
        parse_book_depth({
            "bids": [
                {"price": "0.45", "size": "NaN"},
            ],
            "asks": [],
        })
