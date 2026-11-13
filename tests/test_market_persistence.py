
from decimal import Decimal
from unittest.mock import Mock

import pytest

from prediction_desk.market_persistence import (
    convert_book_event,
    persist_market_event,
)
from prediction_desk.models import OrderBook
from prediction_desk.polymarket_stream import (
    MarketBookEvent,
    MarketPriceChange,
)


def sample_book():
    return MarketBookEvent(
        token_id="123456",
        timestamp_ms=1793140000000,
        bids=((Decimal("0.45"), Decimal("100")),),
        asks=((Decimal("0.47"), Decimal("80")),),
        book_hash="test-hash",
    )


def test_convert_book_event():
    book = convert_book_event(sample_book())

    assert isinstance(book, OrderBook)
    assert book.token_id == "123456"
    assert book.best_bid == Decimal("0.45")
    assert book.best_ask == Decimal("0.47")
    assert book.spread == Decimal("0.02")


def test_persist_full_book():
    storage = Mock()
    storage.save_order_book.return_value = True

    result = persist_market_event(storage, sample_book())

    assert result.event_type == "book"
    assert result.inserted is True

    kwargs = storage.save_order_book.call_args.kwargs

    assert kwargs["source_timestamp_ms"] == 1793140000000
    assert kwargs["book_hash"] == "test-hash"
    assert isinstance(kwargs["book"], OrderBook)

    storage.save_market_price_change.assert_not_called()
    storage.save_atomic_market_price_change.assert_not_called()


def test_persist_price_change_separately():
    storage = Mock()
    storage.save_atomic_market_price_change.return_value = True

    event = MarketPriceChange(
        token_id="123456",
        best_bid=Decimal("0.50"),
        best_ask=Decimal("0.51"),
    )

    result = persist_market_event(storage, event)

    assert result.event_type == "price_change"
    assert result.inserted is True

    storage.save_atomic_market_price_change.assert_called_once()
    storage.save_market_price_change.assert_not_called()
    storage.save_order_book.assert_not_called()


def test_duplicate_book_is_reported():
    storage = Mock()
    storage.save_order_book.return_value = False

    result = persist_market_event(storage, sample_book())

    assert result.inserted is False


def test_missing_book_hash_rejected():
    storage = Mock()

    event = MarketBookEvent(
        token_id="123456",
        timestamp_ms=1793140000000,
        bids=((Decimal("0.45"), Decimal("100")),),
        asks=((Decimal("0.47"), Decimal("80")),),
        book_hash=None,
    )

    with pytest.raises(ValueError, match="hash"):
        persist_market_event(storage, event)

    storage.save_order_book.assert_not_called()


def test_invalid_book_level_rejected():
    storage = Mock()

    event = MarketBookEvent(
        token_id="123456",
        timestamp_ms=1793140000000,
        bids=((Decimal("0.45"), Decimal("0")),),
        asks=((Decimal("0.47"), Decimal("80")),),
        book_hash="test-hash",
    )

    with pytest.raises(ValueError):
        persist_market_event(storage, event)

    storage.save_order_book.assert_not_called()
