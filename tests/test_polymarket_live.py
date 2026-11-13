
import json
from unittest.mock import Mock

import pytest

from prediction_desk.polymarket_live import collect_live_market
from prediction_desk.storage import Storage


UP_TOKEN = "123456"
DOWN_TOKEN = "789012"


def book_message(token_id, timestamp, book_hash):
    return json.dumps(
        {
            "event_type": "book",
            "asset_id": token_id,
            "timestamp": str(timestamp),
            "hash": book_hash,
            "bids": [
                {"price": "0.45", "size": "100"},
            ],
            "asks": [
                {"price": "0.47", "size": "80"},
            ],
        }
    )


def price_message(token_id):
    return json.dumps(
        {
            "event_type": "price_change",
            "timestamp": "1001",
            "price_changes": [
                {
                    "asset_id": token_id,
                    "price": "0.46",
                    "size": "50",
                    "side": "BUY",
                    "best_bid": "0.46",
                    "best_ask": "0.47",
                }
            ],
        }
    )


class FakeWebSocket:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def send(self, message):
        self.sent.append(message)

    def recv(self, timeout=None):
        try:
            return next(self.messages)
        except StopIteration:
            raise TimeoutError


def run_collector(messages, storage, *, max_messages=None):
    websocket = FakeWebSocket(messages)

    # A deterministic clock prevents waiting for real time.
    ticks = iter(range(1000))

    def clock():
        return next(ticks)

    result = collect_live_market(
        token_ids=[UP_TOKEN, DOWN_TOKEN],
        duration_seconds=10,
        max_messages=max_messages or len(messages),
        storage=storage,
        connect_fn=lambda *args, **kwargs: websocket,
        clock_fn=clock,
    )

    return result, websocket


def test_subscription_and_book_persistence(tmp_path):
    with Storage(tmp_path / "book.db") as storage:
        storage.initialize()

        result, websocket = run_collector(
            [book_message(UP_TOKEN, 1000, "hash-1")],
            storage,
        )

        assert result.messages_received == 1
        assert result.book_events == 1
        assert result.books_inserted == 1

        subscription = json.loads(websocket.sent[0])

        assert subscription["type"] == "market"
        assert set(subscription["assets_ids"]) == {
            UP_TOKEN,
            DOWN_TOKEN,
        }

        row = storage.connection.execute(
            """
            SELECT
                stream_session_id,
                message_sequence
            FROM order_book_snapshots
            """
        ).fetchone()

        assert row is not None
        assert row[0] is not None
        assert row[1] == 1

        session = storage.connection.execute(
            """
            SELECT status, ended_at_utc
            FROM polymarket_stream_sessions
            WHERE id = ?
            """,
            (row[0],),
        ).fetchone()

        assert session[0] == "completed"
        assert session[1] is not None


def test_price_changes_are_not_full_books(tmp_path):
    with Storage(tmp_path / "changes.db") as storage:
        storage.initialize()

        result, _ = run_collector(
            [price_message(UP_TOKEN)],
            storage,
        )

        assert result.price_changes == 1
        assert result.price_changes_inserted == 1
        assert result.books_inserted == 0
        assert storage.count_snapshots() == 0
        assert storage.count_market_price_changes() == 1

        level = storage.connection.execute(
            """
            SELECT stream_session_id, message_sequence
            FROM market_level_updates
            """
        ).fetchone()

        assert level is not None
        assert level[0] is not None
        assert level[1] == 1


def test_duplicate_book_counted(tmp_path):
    with Storage(tmp_path / "duplicates.db") as storage:
        storage.initialize()

        message = book_message(
            UP_TOKEN,
            1000,
            "hash-1",
        )

        result, _ = run_collector(
            [message, message],
            storage,
        )

        assert result.messages_received == 2
        assert result.book_events == 2
        assert result.books_inserted == 1
        assert result.duplicate_books == 1
        assert storage.count_snapshots() == 1


def test_mixed_event_session(tmp_path):
    with Storage(tmp_path / "mixed.db") as storage:
        storage.initialize()

        messages = [
            book_message(UP_TOKEN, 1000, "hash-1"),
            book_message(DOWN_TOKEN, 1001, "hash-2"),
            price_message(UP_TOKEN),
            "PONG",
        ]

        result, _ = run_collector(
            messages,
            storage,
        )

        assert result.messages_received == 4
        assert result.book_events == 2
        assert result.price_changes == 1
        assert result.ignored_messages == 1

        assert result.books_inserted == 2
        assert result.price_changes_inserted == 1

        assert storage.count_snapshots() == 2
        assert storage.count_market_price_changes() == 1

        sequences = storage.connection.execute(
            """
            SELECT message_sequence
            FROM order_book_snapshots
            ORDER BY id
            """
        ).fetchall()

        assert sequences == [(1,), (2,)]

        change_sequence = storage.connection.execute(
            """
            SELECT message_sequence
            FROM market_level_updates
            """
        ).fetchone()

        assert change_sequence == (3,)

        sessions = storage.connection.execute(
            """
            SELECT id, status, ended_at_utc
            FROM polymarket_stream_sessions
            """
        ).fetchall()

        assert len(sessions) == 1
        assert sessions[0][1] == "completed"
        assert sessions[0][2] is not None
