
from decimal import Decimal

import pytest

from prediction_desk.models import OrderBook, OrderBookLevel
from prediction_desk.storage import Storage
from prediction_desk.historical_replay import (
    replay_from_snapshot,
)


def D(value):
    return Decimal(str(value))


@pytest.fixture
def storage(tmp_path):
    with Storage(tmp_path / "replay.db") as db:
        db.initialize()
        yield db


def seed_snapshot(storage):
    book = OrderBook(
        token_id="123456789",
        bids=(
            OrderBookLevel(D("0.45"), D("100")),
        ),
        asks=(
            OrderBookLevel(D("0.55"), D("150")),
        ),
    )

    storage.save_order_book(
        book=book,
        source_timestamp_ms=1000,
        observed_at_utc="2026-10-31T12:00:00Z",
        book_hash="test-hash",
    )

    return storage.connection.execute(
        "SELECT id FROM order_book_snapshots"
    ).fetchone()[0]


def add_update(
    storage,
    timestamp,
    side,
    price,
    size,
    token_id="123456789",
):
    storage.save_market_level_update(
        token_id=token_id,
        price=D(price),
        size=D(size),
        side=side,
        observed_at_utc="2026-10-31T12:00:01Z",
        source_timestamp_ms=timestamp,
    )


def test_replay_absolute_replacement(storage):
    snapshot_id = seed_snapshot(storage)

    add_update(storage, 1001, "BUY", "0.45", "75")

    result = replay_from_snapshot(
        storage.connection,
        snapshot_id,
    )

    assert result.updates_applied == 1
    assert result.final_state.bid_depth == D("75")
    assert result.first_update_ms == 1001
    assert result.last_update_ms == 1001
    assert result.continuity_verified is False
    assert result.absolute_size_semantics_verified is False


def test_replay_zero_size_removal(storage):
    snapshot_id = seed_snapshot(storage)

    add_update(storage, 1001, "BUY", "0.45", "0")

    result = replay_from_snapshot(
        storage.connection,
        snapshot_id,
    )

    assert result.final_state.best_bid is None
    assert result.final_state.bid_depth == D("0")


def test_replay_filters_token_and_timestamp(storage):
    snapshot_id = seed_snapshot(storage)

    add_update(storage, 999, "BUY", "0.45", "20")
    add_update(storage, 1000, "BUY", "0.45", "30")
    add_update(
        storage, 1001, "BUY", "0.45", "40",
        token_id="987654321",
    )

    result = replay_from_snapshot(
        storage.connection,
        snapshot_id,
    )

    assert result.updates_applied == 0
    assert result.final_state.bid_depth == D("100")


def test_replay_orders_updates_by_timestamp(storage):
    snapshot_id = seed_snapshot(storage)

    add_update(storage, 1003, "BUY", "0.45", "30")
    add_update(storage, 1001, "BUY", "0.45", "80")
    add_update(storage, 1002, "BUY", "0.45", "60")

    result = replay_from_snapshot(
        storage.connection,
        snapshot_id,
    )

    assert result.updates_applied == 3
    assert result.final_state.bid_depth == D("30")


def test_replay_rejects_truncated_result(storage):
    snapshot_id = seed_snapshot(storage)

    add_update(storage, 1001, "BUY", "0.45", "80")
    add_update(storage, 1002, "BUY", "0.45", "60")

    with pytest.raises(ValueError, match="max_updates"):
        replay_from_snapshot(
            storage.connection,
            snapshot_id,
            max_updates=1,
        )
