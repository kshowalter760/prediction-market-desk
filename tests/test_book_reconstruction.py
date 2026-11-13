
from decimal import Decimal

import pytest

from prediction_desk.book_reconstruction import (
    BookReconstructor,
    ReconstructionUpdate,
)


def D(value):
    return Decimal(str(value))


def make_book():
    return BookReconstructor(
        timestamp_ms=1000,
        bids=[
            (D("0.45"), D("100")),
            (D("0.44"), D("200")),
        ],
        asks=[
            (D("0.55"), D("150")),
            (D("0.56"), D("50")),
        ],
    )


def test_initial_snapshot_metrics():
    state = make_book().state()

    assert state.best_bid == D("0.45")
    assert state.best_ask == D("0.55")
    assert state.spread == D("0.10")
    assert state.bid_depth == D("300")
    assert state.ask_depth == D("200")
    assert state.imbalance == D("0.2")


def test_absolute_size_replacement():
    book = make_book()

    book.apply(
        ReconstructionUpdate(
            timestamp_ms=1001,
            side="BUY",
            price=D("0.45"),
            size=D("75"),
        )
    )

    assert book.state().bid_depth == D("275")


def test_new_price_level():
    book = make_book()

    book.apply(
        ReconstructionUpdate(
            timestamp_ms=1001,
            side="BUY",
            price=D("0.46"),
            size=D("25"),
        )
    )

    assert book.state().best_bid == D("0.46")


def test_zero_size_removes_level():
    book = make_book()

    book.apply(
        ReconstructionUpdate(
            timestamp_ms=1001,
            side="BUY",
            price=D("0.45"),
            size=D("0"),
        )
    )

    assert book.state().best_bid == D("0.44")


def test_out_of_order_update_rejected():
    book = make_book()

    with pytest.raises(ValueError):
        book.apply(
            ReconstructionUpdate(
                timestamp_ms=999,
                side="BUY",
                price=D("0.45"),
                size=D("50"),
            )
        )


def test_equal_timestamp_allowed():
    book = make_book()

    book.apply(
        ReconstructionUpdate(
            timestamp_ms=1000,
            side="BUY",
            price=D("0.45"),
            size=D("90"),
        )
    )

    assert book.state().bid_depth == D("290")


def test_crossed_update_rolls_back():
    book = make_book()
    original = book.state()

    with pytest.raises(ValueError):
        book.apply(
            ReconstructionUpdate(
                timestamp_ms=1001,
                side="BUY",
                price=D("0.60"),
                size=D("10"),
            )
        )

    assert book.state() == original


def test_duplicate_snapshot_level_rejected():
    with pytest.raises(ValueError):
        BookReconstructor(
            timestamp_ms=1000,
            bids=[
                (D("0.45"), D("100")),
                (D("0.45"), D("200")),
            ],
            asks=[],
        )


def test_empty_book_is_valid():
    book = BookReconstructor(
        timestamp_ms=1000,
        bids=[],
        asks=[],
    )

    state = book.state()

    assert state.best_bid is None
    assert state.best_ask is None
    assert state.spread is None
    assert state.imbalance is None


def test_invalid_negative_size_rejected():
    book = make_book()

    with pytest.raises(ValueError):
        book.apply(
            ReconstructionUpdate(
                timestamp_ms=1001,
                side="SELL",
                price=D("0.55"),
                size=D("-10"),
            )
        )


def test_ask_side_replacement():
    book = make_book()

    book.apply(
        ReconstructionUpdate(
            timestamp_ms=1001,
            side="SELL",
            price=D("0.55"),
            size=D("100"),
        )
    )

    assert book.state().ask_depth == D("150")


def test_book_state_is_sorted():
    state = make_book().state()

    assert [price for price, _ in state.bids] == [
        D("0.45"),
        D("0.44"),
    ]

    assert [price for price, _ in state.asks] == [
        D("0.55"),
        D("0.56"),
    ]
