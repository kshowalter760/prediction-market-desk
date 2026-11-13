
import sqlite3

import pytest

from prediction_desk.snapshot_pair_verification import (
    verify_snapshot_pair,
)


@pytest.fixture
def connection():
    db = sqlite3.connect(":memory:")

    db.executescript(
        """
        CREATE TABLE order_book_snapshots (
            id INTEGER PRIMARY KEY,
            token_id TEXT NOT NULL,
            source_timestamp_ms INTEGER NOT NULL,
            observed_at_utc TEXT NOT NULL,
            best_bid TEXT,
            best_ask TEXT,
            spread TEXT,
            book_hash TEXT NOT NULL,
            stream_session_id INTEGER,
            message_sequence INTEGER
        );

        CREATE TABLE order_book_levels (
            id INTEGER PRIMARY KEY,
            snapshot_id INTEGER NOT NULL,
            side TEXT NOT NULL,
            price TEXT NOT NULL,
            size TEXT NOT NULL
        );

        CREATE TABLE market_level_updates (
            id INTEGER PRIMARY KEY,
            token_id TEXT NOT NULL,
            source_timestamp_ms INTEGER,
            observed_at_utc TEXT NOT NULL,
            price TEXT NOT NULL,
            size TEXT NOT NULL,
            side TEXT NOT NULL,
            stream_session_id INTEGER,
            message_sequence INTEGER
        );
        """
    )

    yield db
    db.close()


def add_snapshot(
    db,
    snapshot_id,
    sequence,
    bid_size,
    *,
    token="TOKEN_A",
    session=5,
):
    timestamp = 1000 + sequence * 100

    db.execute(
        """
        INSERT INTO order_book_snapshots
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            token,
            timestamp,
            "2026-11-01T00:00:00Z",
            "0.49",
            "0.51",
            "0.02",
            f"hash_{snapshot_id}",
            session,
            sequence,
        ),
    )

    db.executemany(
        """
        INSERT INTO order_book_levels
        (snapshot_id, side, price, size)
        VALUES (?, ?, ?, ?)
        """,
        [
            (snapshot_id, "BUY", "0.49", str(bid_size)),
            (snapshot_id, "SELL", "0.51", "10"),
        ],
    )


def add_update(db, sequence, size, *, token="TOKEN_A"):
    db.execute(
        """
        INSERT INTO market_level_updates
        (
            token_id,
            source_timestamp_ms,
            observed_at_utc,
            price,
            size,
            side,
            stream_session_id,
            message_sequence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            token,
            1000 + sequence * 100,
            "2026-11-01T00:00:00Z",
            "0.49",
            str(size),
            "BUY",
            5,
            sequence,
        ),
    )


def test_matching_snapshot_pair(connection):
    add_snapshot(connection, 1, 1, 10)
    add_snapshot(connection, 2, 3, 15)
    add_update(connection, 2, 15)

    report = verify_snapshot_pair(connection, 1, 2)

    assert report.depth_matches
    assert report.independently_verified
    assert report.updates_applied == 1
    assert not report.continuity_verified


def test_mismatching_depth(connection):
    add_snapshot(connection, 1, 1, 10)
    add_snapshot(connection, 2, 3, 20)
    add_update(connection, 2, 15)

    report = verify_snapshot_pair(connection, 1, 2)

    assert not report.depth_matches
    assert not report.independently_verified


def test_different_tokens_rejected(connection):
    add_snapshot(connection, 1, 1, 10)
    add_snapshot(
        connection, 2, 3, 15, token="TOKEN_B"
    )

    with pytest.raises(ValueError, match="different tokens"):
        verify_snapshot_pair(connection, 1, 2)


def test_different_sessions_rejected(connection):
    add_snapshot(connection, 1, 1, 10)
    add_snapshot(connection, 2, 3, 15, session=6)

    with pytest.raises(ValueError, match="different sessions"):
        verify_snapshot_pair(connection, 1, 2)


def test_reversed_sequence_rejected(connection):
    add_snapshot(connection, 1, 3, 10)
    add_snapshot(connection, 2, 1, 15)

    with pytest.raises(ValueError, match="later sequence"):
        verify_snapshot_pair(connection, 1, 2)


def test_missing_snapshot_rejected(connection):
    add_snapshot(connection, 1, 1, 10)

    with pytest.raises(ValueError, match="Snapshot not found"):
        verify_snapshot_pair(connection, 1, 999)


def test_update_limit_rejected(connection):
    add_snapshot(connection, 1, 1, 10)
    add_snapshot(connection, 2, 4, 20)
    add_update(connection, 2, 15)
    add_update(connection, 3, 20)

    with pytest.raises(ValueError, match="max_updates"):
        verify_snapshot_pair(
            connection, 1, 2, max_updates=1
        )


def test_later_session_updates_excluded(connection):
    add_snapshot(connection, 1, 1, 10)
    add_snapshot(connection, 2, 3, 15)
    add_update(connection, 2, 15)

    connection.execute(
        """
        INSERT INTO market_level_updates
        (
            token_id,
            source_timestamp_ms,
            observed_at_utc,
            price,
            size,
            side,
            stream_session_id,
            message_sequence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "TOKEN_A",
            1200,
            "2026-11-01T00:00:00Z",
            "0.49",
            "999",
            "BUY",
            6,
            2,
        ),
    )

    report = verify_snapshot_pair(connection, 1, 2)

    assert report.updates_applied == 1
    assert report.depth_matches
