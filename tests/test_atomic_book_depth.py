
from decimal import Decimal

import pytest

from prediction_desk.models import OrderBook, OrderBookLevel
from prediction_desk.storage import Storage


def make_book():
    return OrderBook(
        token_id="123456789",
        bids=(
            OrderBookLevel(
                price=Decimal("0.45"),
                size=Decimal("100"),
            ),
            OrderBookLevel(
                price=Decimal("0.44"),
                size=Decimal("200"),
            ),
        ),
        asks=(
            OrderBookLevel(
                price=Decimal("0.55"),
                size=Decimal("150"),
            ),
        ),
    )


@pytest.fixture
def storage(tmp_path):
    with Storage(tmp_path / "test.db") as instance:
        instance.initialize()
        yield instance


def test_snapshot_and_levels_saved(storage):
    inserted = storage.save_order_book(
        book=make_book(),
        source_timestamp_ms=1000,
        observed_at_utc="2026-10-31T12:00:00Z",
        book_hash="hash-1",
    )

    assert inserted is True

    snapshots = storage.connection.execute(
        "SELECT COUNT(*) FROM order_book_snapshots"
    ).fetchone()[0]

    levels = storage.connection.execute(
        "SELECT COUNT(*) FROM order_book_levels"
    ).fetchone()[0]

    assert snapshots == 1
    assert levels == 3


def test_duplicate_snapshot_does_not_duplicate_levels(storage):
    kwargs = {
        "book": make_book(),
        "source_timestamp_ms": 1000,
        "observed_at_utc": "2026-10-31T12:00:00Z",
        "book_hash": "hash-1",
    }

    assert storage.save_order_book(**kwargs) is True
    assert storage.save_order_book(**kwargs) is False

    assert storage.connection.execute(
        "SELECT COUNT(*) FROM order_book_snapshots"
    ).fetchone()[0] == 1

    assert storage.connection.execute(
        "SELECT COUNT(*) FROM order_book_levels"
    ).fetchone()[0] == 3


def test_invalid_level_rejected_without_writes(storage):
    book = OrderBook(
        token_id="123456789",
        bids=(
            OrderBookLevel(
                price=Decimal("0.45"),
                size=Decimal("-5"),
            ),
        ),
        asks=(),
    )

    with pytest.raises(ValueError):
        storage.save_order_book(
            book=book,
            source_timestamp_ms=1000,
            observed_at_utc="2026-10-31T12:00:00Z",
            book_hash="hash-1",
        )

    assert storage.connection.execute(
        "SELECT COUNT(*) FROM order_book_snapshots"
    ).fetchone()[0] == 0


def test_database_failure_rolls_back_snapshot(storage):
    storage.connection.execute(
        """
        CREATE TRIGGER fail_level_insert
        BEFORE INSERT ON order_book_levels
        BEGIN
            SELECT RAISE(ABORT, 'forced failure');
        END
        """
    )
    storage.connection.commit()

    with pytest.raises(Exception, match="forced failure"):
        storage.save_order_book(
            book=make_book(),
            source_timestamp_ms=1000,
            observed_at_utc="2026-10-31T12:00:00Z",
            book_hash="hash-1",
        )

    assert storage.connection.execute(
        "SELECT COUNT(*) FROM order_book_snapshots"
    ).fetchone()[0] == 0

    assert storage.connection.execute(
        "SELECT COUNT(*) FROM order_book_levels"
    ).fetchone()[0] == 0
