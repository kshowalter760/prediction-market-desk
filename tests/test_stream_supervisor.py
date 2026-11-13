
from collections import deque

from prediction_desk.storage import Storage
from prediction_desk.stream_supervisor import (
    run_supervised_stream,
)


def trade_message(trade_id):
    return {
        "type": "match",
        "product_id": "BTC-USD",
        "trade_id": trade_id,
        "time": "2026-10-27T01:00:00Z",
        "price": "80000",
        "size": "0.01",
    }


class FakeWebSocket:
    def __init__(self, messages):
        self.messages = deque(messages)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def send(self, message):
        pass

    def recv(self, timeout):
        if not self.messages:
            raise TimeoutError()

        value = self.messages.popleft()

        if isinstance(value, Exception):
            raise value

        return value


def test_successful_session(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        result = run_supervised_stream(
            storage,
            max_messages=2,
            connect_fn=lambda *a, **k: FakeWebSocket([
                trade_message(101),
                trade_message(102),
            ]),
            sleep_fn=lambda _: None,
        )

        assert result.status == "completed"
        assert result.termination_reason == "message_limit"
        assert result.connection_attempts == 1
        assert result.trades_inserted == 2

        latest = storage.get_latest_spot_stream_session()
        assert latest["status"] == "completed"
        assert latest["trades_inserted"] == 2


def test_reconnects_after_failure(tmp_path):
    attempts = iter([
        OSError("temporary disconnect"),
        FakeWebSocket([
            trade_message(101),
            trade_message(102),
        ]),
    ])

    def fake_connect(*args, **kwargs):
        value = next(attempts)

        if isinstance(value, Exception):
            raise value

        return value

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        result = run_supervised_stream(
            storage,
            max_messages=2,
            max_attempts=3,
            connect_fn=fake_connect,
            sleep_fn=lambda _: None,
        )

        assert result.status == "completed"
        assert result.connection_attempts == 2
        assert result.trades_inserted == 2


def test_attempts_exhausted(tmp_path):
    def always_fail(*args, **kwargs):
        raise OSError("offline")

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        result = run_supervised_stream(
            storage,
            max_messages=2,
            max_attempts=2,
            connect_fn=always_fail,
            sleep_fn=lambda _: None,
        )

        assert result.status == "failed"
        assert result.termination_reason == "attempts_exhausted"
        assert result.connection_attempts == 2

        latest = storage.get_latest_spot_stream_session()
        assert latest["status"] == "failed"


def test_timeout_is_normal_completion(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        result = run_supervised_stream(
            storage,
            max_messages=10,
            connect_fn=lambda *a, **k: FakeWebSocket([]),
            sleep_fn=lambda _: None,
        )

        assert result.status == "completed"
        assert result.termination_reason == "receive_timeout"
        assert result.messages_received == 0
