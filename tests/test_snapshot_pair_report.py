
import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from prediction_desk.snapshot_pair_report import (
    verify_session_snapshot_pairs,
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

    yield db
    db.close()


def add_snapshot(db, snapshot_id, token, session, sequence):
    db.execute(
        """
        INSERT INTO order_book_snapshots
        (id, token_id, stream_session_id, message_sequence)
        VALUES (?, ?, ?, ?)
        """,
        (snapshot_id, token, session, sequence),
    )


def test_single_snapshot_per_token_has_no_pairs(connection):
    add_snapshot(connection, 71, "TOKEN_A", 5, 1)
    add_snapshot(connection, 72, "TOKEN_B", 5, 1)

    report = verify_session_snapshot_pairs(connection, 5)

    assert report.snapshot_count == 2
    assert report.token_count == 2
    assert report.eligible_pair_count == 0
    assert report.results == ()


def test_consecutive_pairs_discovered_per_token(connection):
    for snapshot_id, token, sequence in [
        (63, "TOKEN_A", 1),
        (65, "TOKEN_A", 10),
        (67, "TOKEN_A", 20),
        (64, "TOKEN_B", 1),
        (66, "TOKEN_B", 10),
        (68, "TOKEN_B", 20),
    ]:
        add_snapshot(connection, snapshot_id, token, 3, sequence)

    with patch(
        "prediction_desk.snapshot_pair_report.verify_snapshot_pair",
        return_value=SimpleNamespace(
            independently_verified=True,
            updates_applied=10,
        ),
    ) as verifier:
        report = verify_session_snapshot_pairs(connection, 3)

    assert report.snapshot_count == 6
    assert report.token_count == 2
    assert report.eligible_pair_count == 4
    assert report.matched_pair_count == 4
    assert report.mismatched_pair_count == 0
    assert verifier.call_count == 4

    pairs = {
        (item.initial_snapshot_id, item.final_snapshot_id)
        for item in report.results
    }

    assert pairs == {
        (63, 65),
        (65, 67),
        (64, 66),
        (66, 68),
    }


def test_mismatched_depth_reported(connection):
    add_snapshot(connection, 1, "TOKEN_A", 3, 1)
    add_snapshot(connection, 2, "TOKEN_A", 3, 2)

    with patch(
        "prediction_desk.snapshot_pair_report.verify_snapshot_pair",
        return_value=SimpleNamespace(
            independently_verified=False,
            updates_applied=5,
        ),
    ):
        report = verify_session_snapshot_pairs(connection, 3)

    assert report.matched_pair_count == 0
    assert report.mismatched_pair_count == 1
    assert report.results[0].status == "mismatched"


def test_replay_error_reported(connection):
    add_snapshot(connection, 1, "TOKEN_A", 3, 1)
    add_snapshot(connection, 2, "TOKEN_A", 3, 2)

    with patch(
        "prediction_desk.snapshot_pair_report.verify_snapshot_pair",
        side_effect=ValueError("Replay limit exceeded"),
    ):
        report = verify_session_snapshot_pairs(connection, 3)

    assert report.error_count == 1
    assert report.results[0].status == "error"
    assert "Replay limit" in report.results[0].error


def test_invalid_sequence_reported(connection):
    add_snapshot(connection, 1, "TOKEN_A", 3, 1)
    add_snapshot(connection, 2, "TOKEN_A", 3, 1)

    report = verify_session_snapshot_pairs(connection, 3)

    assert report.error_count == 1
    assert report.results[0].status == "invalid_sequence"


def test_other_sessions_excluded(connection):
    add_snapshot(connection, 1, "TOKEN_A", 3, 1)
    add_snapshot(connection, 2, "TOKEN_A", 4, 2)

    report = verify_session_snapshot_pairs(connection, 3)

    assert report.snapshot_count == 1
    assert report.eligible_pair_count == 0


def test_invalid_session_id_rejected(connection):
    with pytest.raises(ValueError, match="Invalid session ID"):
        verify_session_snapshot_pairs(connection, 0)


def test_invalid_update_limit_rejected(connection):
    with pytest.raises(ValueError, match="max_updates"):
        verify_session_snapshot_pairs(
            connection,
            3,
            max_updates=0,
        )
