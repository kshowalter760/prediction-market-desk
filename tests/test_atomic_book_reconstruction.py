
from decimal import Decimal

import pytest

from prediction_desk.book_reconstruction import (
    BookReconstructor,
    ReconstructionUpdate,
)


D = Decimal
TIMESTAMP = 1793571841277


def make_up_book():
    return BookReconstructor(
        timestamp_ms=TIMESTAMP - 1,
        bids=[
            (D("0.01"), D("14")),
            (D("0.001"), D("100")),
        ],
        asks=[
            (D("0.02"), D("20")),
        ],
    )


def make_down_book():
    return BookReconstructor(
        timestamp_ms=TIMESTAMP - 1,
        bids=[
            (D("0.98"), D("20")),
        ],
        asks=[
            (D("0.99"), D("14")),
            (D("0.999"), D("100")),
        ],
    )


def update(side, price, size, timestamp=TIMESTAMP):
    return ReconstructionUpdate(
        timestamp_ms=timestamp,
        side=side,
        price=D(price),
        size=D(size),
    )


def test_up_token_atomic_transition():
    book = make_up_book()

    book.apply_batch([
        update("SELL", "0.01", "6"),
        update("BUY", "0.01", "0"),
    ])

    state = book.state()

    assert state.best_bid == D("0.001")
    assert state.best_ask == D("0.01")
    assert (D("0.01"), D("6")) in state.asks
    assert D("0.01") not in dict(state.bids)


def test_down_token_atomic_transition():
    book = make_down_book()

    book.apply_batch([
        update("BUY", "0.99", "6"),
        update("SELL", "0.99", "0"),
    ])

    state = book.state()

    assert state.best_bid == D("0.99")
    assert state.best_ask == D("0.999")
    assert (D("0.99"), D("6")) in state.bids
    assert D("0.99") not in dict(state.asks)


def test_invalid_batch_rolls_back():
    book = make_up_book()
    before = book.state()

    with pytest.raises(
        ValueError,
        match="Locked or crossed",
    ):
        book.apply_batch([
            update("SELL", "0.01", "6"),
        ])

    assert book.state() == before


def test_invalid_update_rolls_back_entire_batch():
    book = make_up_book()
    before = book.state()

    with pytest.raises(
        ValueError,
        match="Invalid order-book price",
    ):
        book.apply_batch([
            update("BUY", "0.005", "10"),
            update("SELL", "1.5", "3"),
        ])

    assert book.state() == before


def test_out_of_order_batch_rolls_back():
    book = make_up_book()
    before = book.state()

    with pytest.raises(
        ValueError,
        match="Out-of-order",
    ):
        book.apply_batch([
            update(
                "BUY",
                "0.005",
                "10",
                timestamp=TIMESTAMP,
            ),
            update(
                "BUY",
                "0.006",
                "10",
                timestamp=TIMESTAMP - 2,
            ),
        ])

    assert book.state() == before


def test_empty_batch_is_no_op():
    book = make_up_book()
    before = book.state()

    book.apply_batch([])

    assert book.state() == before


def test_single_apply_remains_strict():
    book = make_up_book()

    with pytest.raises(
        ValueError,
        match="Locked or crossed",
    ):
        book.apply(
            update("SELL", "0.01", "6")
        )
