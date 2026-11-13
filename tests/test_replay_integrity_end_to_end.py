from decimal import Decimal
import sqlite3

import pytest

from prediction_desk.replay_integrity import (
    audit_session,
    verify_snapshot_pair,
)


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")

    connection.executescript(
        """
        CREATE TABLE order_book_snapshots (
            id INTEGER PRIMARY KEY,
            token_id TEXT NOT NULL,
            source_timestamp_ms INTEGER NOT NULL,
            best_bid TEXT,
            best_ask TEXT,
            spread TEXT,
            stream_session_id INTEGER,
            message_sequence INTEGER
        );

        CREATE TABLE order_book_levels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            side TEXT NOT NULL
                CHECK (side IN ('BUY', 'SELL')),
            price TEXT NOT NULL,
            size TEXT NOT NULL,
            FOREIGN KEY (snapshot_id)
                REFERENCES order_book_snapshots(id)
                ON DELETE CASCADE,
            UNIQUE (snapshot_id, side, price)
        );

        CREATE TABLE market_level_updates (
            id INTEGER PRIMARY KEY,
            token_id TEXT NOT NULL,
            source_timestamp_ms INTEGER,
            side TEXT NOT NULL,
            price TEXT NOT NULL,
            size TEXT NOT NULL,
            stream_session_id INTEGER,
            message_sequence INTEGER
        );
        """
    )

    yield connection
    connection.close()


def insert_snapshot(
    db,
    snapshot_id,
    session_id,
    sequence,
    timestamp,
    bids,
    asks,
    token="TOKEN_A",
):

    best_bid = max(
        (Decimal(price) for price, _ in bids),
        default=None,
    )

    best_ask = min(
        (Decimal(price) for price, _ in asks),
        default=None,
    )

    spread = (
        str(best_ask - best_bid)
        if best_bid is not None and best_ask is not None
        else None
    )


    db.execute(
        """
        INSERT INTO order_book_snapshots
        (
            id, token_id, source_timestamp_ms,
            best_bid, best_ask, spread,
            stream_session_id, message_sequence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            token,
            timestamp,
            str(best_bid) if best_bid is not None else None,
            str(best_ask) if best_ask is not None else None,
            spread,
            session_id,
            sequence,
        ),
    )

    for side, levels in (
        ("BUY", bids),
        ("SELL", asks),
    ):
        for price, size in levels:
            db.execute(
                """
                INSERT INTO order_book_levels
                (snapshot_id, side, price, size)
                VALUES (?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    side,
                    str(price),
                    str(size),
                ),
            )


def insert_update(
    db,
    update_id,
    session_id,
    sequence,
    timestamp,
    side,
    price,
    size,
    token="TOKEN_A",
):
    db.execute(
        """
        INSERT INTO market_level_updates
        (
            id, token_id, source_timestamp_ms,
            side, price, size,
            stream_session_id, message_sequence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            update_id,
            token,
            timestamp,
            side,
            str(price),
            str(size),
            session_id,
            sequence,
        ),
    )


def seed_atomic_transition(db):
    insert_snapshot(
        db,
        snapshot_id=1,
        session_id=10,
        sequence=1,
        timestamp=1000,
        bids=[
            ("0.01", "14"),
            ("0.001", "100"),
        ],
        asks=[
            ("0.02", "20"),
        ],
    )

    # Add new ask before removing the old bid.
    # The intermediate state is locked.
    insert_update(
        db, 1, 10, 2, 1100,
        "SELL", "0.01", "6",
    )
    insert_update(
        db, 2, 10, 3, 1100,
        "BUY", "0.01", "0",
    )

    insert_snapshot(
        db,
        snapshot_id=2,
        session_id=10,
        sequence=4,
        timestamp=1100,
        bids=[
            ("0.001", "100"),
        ],
        asks=[
            ("0.01", "6"),
            ("0.02", "20"),
        ],
    )


def test_atomic_replay_exact_match(db):
    seed_atomic_transition(db)

    result = verify_snapshot_pair(db, 1, 2)

    assert result.exact_match
    assert result.updates_selected == 2
    assert result.updates_applied == 2
    assert result.bid_differences == 0
    assert result.ask_differences == 0
    assert result.error is None


def test_corrupted_destination_depth_detected(db):
    seed_atomic_transition(db)

    db.execute(
        """
        UPDATE order_book_levels
        SET size = '999'
        WHERE snapshot_id = 2
          AND side = 'SELL'
          AND price = '0.01'
        """
    )

    result = verify_snapshot_pair(db, 1, 2)

    assert not result.exact_match
    assert result.ask_differences == 1
    assert result.bid_differences == 0


def test_cross_session_updates_excluded(db):
    seed_atomic_transition(db)

    # Same token and overlapping timestamp,
    # but belongs to another session.
    insert_update(
        db, 3, 99, 2, 1100,
        "SELL", "0.02", "999",
    )

    result = verify_snapshot_pair(db, 1, 2)

    assert result.exact_match
    assert result.updates_selected == 2


def test_audit_session_end_to_end(db):
    seed_atomic_transition(db)

    results = audit_session(db, 10)

    assert len(results) == 1
    assert results[0].start_snapshot_id == 1
    assert results[0].end_snapshot_id == 2
    assert results[0].exact_match


def test_replay_detects_invalid_intermediate_batch(db):
    seed_atomic_transition(db)

    # Remove the update that clears the old bid.
    db.execute(
        """
        DELETE FROM market_level_updates
        WHERE id = 2
        """
    )

    result = verify_snapshot_pair(db, 1, 2)

    assert not result.exact_match
    assert result.updates_selected == 1
    assert result.updates_applied == 0
    assert result.error is not None
    assert "Locked or crossed" in result.error


def test_cross_session_snapshot_pair_rejected(db):
    seed_atomic_transition(db)

    insert_snapshot(
        db,
        snapshot_id=3,
        session_id=99,
        sequence=5,
        timestamp=1200,
        bids=[("0.10", "10")],
        asks=[("0.20", "10")],
    )

    with pytest.raises(
        ValueError,
        match="Snapshot token/session mismatch",
    ):
        verify_snapshot_pair(db, 1, 3)
