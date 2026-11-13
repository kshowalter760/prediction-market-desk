
import pytest

from prediction_desk.storage import Storage


def test_stream_session_lifecycle(tmp_path):
    with Storage(tmp_path / "sessions.db") as storage:
        storage.initialize()

        session_id = storage.start_spot_stream_session(
            "2026-10-27T01:00:00+00:00"
        )

        running = storage.get_latest_spot_stream_session()

        assert running["id"] == session_id
        assert running["status"] == "running"
        assert running["completed_at_utc"] is None

        storage.finish_spot_stream_session(
            session_id=session_id,
            completed_at_utc="2026-10-27T01:01:00+00:00",
            status="completed",
            termination_reason="message_limit",
            connection_attempts=1,
            messages_received=100,
            trades_received=97,
            trades_inserted=97,
            ignored_messages=3,
            potential_id_gaps=0,
        )

        finished = storage.get_latest_spot_stream_session()

        assert finished["status"] == "completed"
        assert finished["termination_reason"] == "message_limit"
        assert finished["connection_attempts"] == 1
        assert finished["trades_inserted"] == 97


def test_cannot_finish_session_twice(tmp_path):
    with Storage(tmp_path / "sessions.db") as storage:
        storage.initialize()

        session_id = storage.start_spot_stream_session(
            "2026-10-27T01:00:00+00:00"
        )

        arguments = dict(
            session_id=session_id,
            completed_at_utc="2026-10-27T01:01:00+00:00",
            status="completed",
            termination_reason="message_limit",
            connection_attempts=1,
            messages_received=10,
            trades_received=9,
            trades_inserted=9,
            ignored_messages=1,
            potential_id_gaps=0,
        )

        storage.finish_spot_stream_session(**arguments)

        with pytest.raises(ValueError):
            storage.finish_spot_stream_session(
                **arguments
            )


def test_no_sessions_returns_none(tmp_path):
    with Storage(tmp_path / "sessions.db") as storage:
        storage.initialize()

        assert (
            storage.get_latest_spot_stream_session()
            is None
        )
