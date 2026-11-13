
import sqlite3

import pytest

from prediction_desk.stream_sessions import (
    start_stream_session,
    finish_stream_session,
    get_stream_session,
)


@pytest.fixture
def connection():
    db = sqlite3.connect(":memory:")

    db.execute(
        """
        CREATE TABLE polymarket_stream_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at_utc TEXT NOT NULL,
            ended_at_utc TEXT,
            disconnect_reason TEXT,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (
                    status IN (
                        'active',
                        'completed',
                        'disconnected',
                        'failed'
                    )
                )
        )
        """
    )

    yield db
    db.close()


def test_start_session(connection):
    session_id = start_stream_session(connection)
    session = get_stream_session(connection, session_id)

    assert session.session_id == session_id
    assert session.status == "active"
    assert session.ended_at_utc is None


def test_finish_completed_session(connection):
    session_id = start_stream_session(connection)

    finish_stream_session(
        connection,
        session_id,
        status="completed",
    )

    session = get_stream_session(connection, session_id)

    assert session.status == "completed"
    assert session.ended_at_utc is not None


def test_finish_disconnected_session(connection):
    session_id = start_stream_session(connection)

    finish_stream_session(
        connection,
        session_id,
        status="disconnected",
        disconnect_reason="WebSocket connection lost",
    )

    session = get_stream_session(connection, session_id)

    assert session.status == "disconnected"
    assert session.disconnect_reason == (
        "WebSocket connection lost"
    )


def test_cannot_finish_twice(connection):
    session_id = start_stream_session(connection)

    finish_stream_session(
        connection,
        session_id,
        status="completed",
    )

    with pytest.raises(ValueError):
        finish_stream_session(
            connection,
            session_id,
            status="completed",
        )


def test_invalid_final_status(connection):
    session_id = start_stream_session(connection)

    with pytest.raises(ValueError):
        finish_stream_session(
            connection,
            session_id,
            status="active",
        )


def test_missing_session(connection):
    with pytest.raises(ValueError):
        get_stream_session(connection, 999)
