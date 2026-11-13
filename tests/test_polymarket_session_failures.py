
import pytest

from prediction_desk.polymarket_live import collect_live_market
from prediction_desk.storage import Storage


class FailingWebSocket:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def send(self, message):
        pass

    def recv(self, timeout=None):
        raise ConnectionError("Simulated WebSocket disconnect")


def test_websocket_failure_finalizes_stream_session(tmp_path):
    database_path = tmp_path / "failed_session.db"

    with Storage(database_path) as storage:
        storage.initialize()

        with pytest.raises(
            ConnectionError,
            match="Simulated WebSocket disconnect",
        ):
            collect_live_market(
                token_ids=["123456"],
                duration_seconds=10,
                max_messages=10,
                storage=storage,
                connect_fn=lambda *args, **kwargs: FailingWebSocket(),
            )

        sessions = storage.connection.execute(
            """
            SELECT
                status,
                ended_at_utc,
                disconnect_reason
            FROM polymarket_stream_sessions
            """
        ).fetchall()

        assert len(sessions) == 1

        status, ended_at_utc, disconnect_reason = sessions[0]

        assert status == "failed"
        assert ended_at_utc is not None
        assert "ConnectionError" in disconnect_reason
        assert "Simulated WebSocket disconnect" in disconnect_reason
