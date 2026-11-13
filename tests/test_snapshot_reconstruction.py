
from decimal import Decimal

import pytest

from prediction_desk.models import OrderBook, OrderBookLevel
from prediction_desk.snapshot_reconstruction import (
    reconstruct_snapshot,
)
from prediction_desk.storage import Storage


def D(value):
    return Decimal(str(value))


@pytest.fixture
def storage(tmp_path):
    with Storage(tmp_path / "reconstruction.db") as db:
        db.initialize()
        yield db


def save_fixture_snapshot(storage):
    book = OrderBook(
        token_id="123456789",
        bids=(
            OrderBookLevel(D("0.45"), D("100")),
            OrderBookLevel(D("0.44"), D("200")),
        ),
        asks=(
            OrderBookLevel(D("0.55"), D("150")),
        ),
    )

    assert storage.save_order_book(
        book=book,
        source_timestamp_ms=1000,
        observed_at_utc="2026-10-31T12:00:00Z",
        book_hash="test-hash",
    )

    return storage.connection.execute(
        "SELECT id FROM order_book_snapshots"
    ).fetchone()[0]


def test_reconstruct_saved_snapshot(storage):
    snapshot_id = save_fixture_snapshot(storage)

    result = reconstruct_snapshot(
        storage.connection,
        snapshot_id,
    )

    assert result.matches_metadata is True
    assert len(result.reconstructed.bids) == 2
    assert len(result.reconstructed.asks) == 1
    assert result.reconstructed.best_bid == D("0.45")
    assert result.reconstructed.best_ask == D("0.55")
    assert result.reconstructed.bid_depth == D("300")
    assert result.reconstructed.ask_depth == D("150")


def test_missing_snapshot_rejected(storage):
    with pytest.raises(ValueError, match="Snapshot not found"):
        reconstruct_snapshot(storage.connection, 999)


def test_snapshot_without_depth_rejected(storage):
    storage.connection.execute(
        """
        INSERT INTO order_book_snapshots (
            token_id,
            source_timestamp_ms,
            observed_at_utc,
            book_hash
        )
        VALUES (?, ?, ?, ?)
        """,
        ("123456789", 1000, "2026-10-31T12:00:00Z", "old"),
    )
    storage.connection.commit()

    snapshot_id = storage.connection.execute(
        "SELECT id FROM order_book_snapshots"
    ).fetchone()[0]

    with pytest.raises(
        ValueError,
        match="no persisted depth",
    ):
        reconstruct_snapshot(storage.connection, snapshot_id)


def test_metadata_mismatch_detected(storage):
    snapshot_id = save_fixture_snapshot(storage)

    storage.connection.execute(
        """
        UPDATE order_book_snapshots
        SET best_bid = ?
        WHERE id = ?
        """,
        ("0.40", snapshot_id),
    )
    storage.connection.commit()

    result = reconstruct_snapshot(
        storage.connection,
        snapshot_id,
    )

    assert result.matches_metadata is False
    assert result.reconstructed.best_bid == D("0.45")


def test_invalid_snapshot_id_rejected(storage):
    for invalid_id in (0, -1, True, "37"):
        with pytest.raises(ValueError):
            reconstruct_snapshot(
                storage.connection,
                invalid_id,
            )
