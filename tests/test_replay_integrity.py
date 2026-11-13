
import sqlite3

import pytest

from prediction_desk.replay_integrity import (
    audit_session,
    count_differences,
    discover_snapshot_pairs,
    verify_snapshot_pair,
)


@pytest.fixture
def connection():
    db = sqlite3.connect(":memory:")

    db.execute(
        """
        CREATE TABLE order_book_snapshots (
            id INTEGER PRIMARY KEY,
            token_id TEXT NOT NULL,
            stream_session_id INTEGER,
            message_sequence INTEGER
        )
        """
    )

    rows = [
        (1, "TOKEN_A", 10, 1),
        (2, "TOKEN_B", 10, 2),
        (3, "TOKEN_A", 10, 5),
        (4, "TOKEN_B", 10, 6),
        (5, "TOKEN_A", 10, 9),
        (6, "TOKEN_A", 11, 1),
        (7, "TOKEN_A", 11, 5),
    ]

    db.executemany(
        """
        INSERT INTO order_book_snapshots
        (id, token_id, stream_session_id, message_sequence)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )

    yield db
    db.close()


def test_discovers_consecutive_pairs(connection):
    pairs = discover_snapshot_pairs(connection, 10)

    assert pairs == [
        (1, 3),
        (3, 5),
        (2, 4),
    ]


def test_sessions_are_isolated(connection):
    pairs = discover_snapshot_pairs(connection, 11)

    assert pairs == [(6, 7)]


def test_unknown_session_has_no_pairs(connection):
    assert discover_snapshot_pairs(connection, 999) == []


def test_difference_counting():
    from decimal import Decimal

    D = Decimal

    actual = [
        (D("0.40"), D("100")),
        (D("0.39"), D("50")),
    ]

    expected = [
        (D("0.40"), D("100")),
        (D("0.39"), D("75")),
        (D("0.38"), D("20")),
    ]

    assert count_differences(actual, expected) == 2


def test_rejects_cross_session_pair(connection):
    with pytest.raises(
        ValueError,
        match="Snapshot token/session mismatch",
    ):
        verify_snapshot_pair(connection, 1, 7)


def test_audit_coordinator_uses_discovered_pairs(
    connection,
    monkeypatch,
):
    import prediction_desk.replay_integrity as module

    calls = []

    def fake_verify(db, start_id, end_id):
        assert db is connection
        calls.append((start_id, end_id))
        return (start_id, end_id)

    monkeypatch.setattr(
        module,
        "verify_snapshot_pair",
        fake_verify,
    )

    results = audit_session(connection, 10)

    assert results == [
        (1, 3),
        (3, 5),
        (2, 4),
    ]
    assert calls == results

def test_verification_preserves_connection_row_factory(connection):
    connection.row_factory = sqlite3.Row

    with pytest.raises(ValueError, match="Snapshot token/session mismatch"):
        verify_snapshot_pair(connection, 1, 7)

    assert connection.row_factory is sqlite3.Row