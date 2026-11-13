
from decimal import Decimal

import pytest

from prediction_desk.models import OrderBook
from prediction_desk.storage import Storage


def make_book():
    return OrderBook.from_api({
        "asset_id": "123456",
        "bids": [
            {"price": "0.028", "size": "100"},
        ],
        "asks": [
            {"price": "0.029", "size": "200"},
        ],
    })


def test_database_initialization(tmp_path):
    database_path = tmp_path / "test.db"

    with Storage(database_path) as storage:
        storage.initialize()

        assert database_path.exists()
        assert storage.count_snapshots() == 0


def test_save_order_book(tmp_path):
    database_path = tmp_path / "test.db"

    with Storage(database_path) as storage:
        storage.initialize()

        inserted = storage.save_order_book(
            book=make_book(),
            source_timestamp_ms=1792979068387,
            observed_at_utc="2026-10-25T19:00:00Z",
            book_hash="abc123",
        )

        assert inserted is True
        assert storage.count_snapshots() == 1


def test_duplicate_snapshot_ignored(tmp_path):
    database_path = tmp_path / "test.db"

    with Storage(database_path) as storage:
        storage.initialize()

        for _ in range(2):
            storage.save_order_book(
                book=make_book(),
                source_timestamp_ms=1792979068387,
                observed_at_utc="2026-10-25T19:00:00Z",
                book_hash="abc123",
            )

        assert storage.count_snapshots() == 1


def test_new_snapshot_inserted(tmp_path):
    database_path = tmp_path / "test.db"

    with Storage(database_path) as storage:
        storage.initialize()

        for timestamp in (1792979068387, 1792979069387):
            storage.save_order_book(
                book=make_book(),
                source_timestamp_ms=timestamp,
                observed_at_utc="2026-10-25T19:00:00Z",
                book_hash="abc123",
            )

        assert storage.count_snapshots() == 2


def test_invalid_timestamp(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        with pytest.raises(ValueError):
            storage.save_order_book(
                book=make_book(),
                source_timestamp_ms=-1,
                observed_at_utc="2026-10-25T19:00:00Z",
                book_hash="abc123",
            )


def test_crossed_order_book_rejected(tmp_path):
    crossed_book = OrderBook.from_api({
        "asset_id": "123456",
        "bids": [
            {"price": "0.6", "size": "100"},
        ],
        "asks": [
            {"price": "0.5", "size": "100"},
        ],
    })

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        with pytest.raises(
            ValueError,
            match="locked or crossed",
        ):
            storage.save_order_book(
                book=crossed_book,
                source_timestamp_ms=1792979068387,
                observed_at_utc="2026-10-25T19:00:00Z",
                book_hash="abc123",
            )
