
from decimal import Decimal

from prediction_desk.storage import Storage
from prediction_desk.models import OrderBook, OrderBookLevel
from prediction_desk.stream_sessions import (
    start_stream_session,
    finish_stream_session,
)


def test_price_change_commits_before_next_book(tmp_path):
    database_path = tmp_path / "transaction_boundary.db"

    with Storage(database_path) as storage:
        storage.initialize()

        session_id = start_stream_session(
            storage.connection
        )

        assert storage.connection.in_transaction is False

        inserted = storage.save_atomic_market_price_change(
            token_id="123456",
            best_bid=Decimal("0.45"),
            best_ask=Decimal("0.47"),
            observed_at_utc="2026-11-01T16:00:00Z",
            source_timestamp_ms=1793548800000,
            price=Decimal("0.45"),
            size=Decimal("100"),
            side="BUY",
            stream_session_id=session_id,
            message_sequence=1,
        )

        assert inserted is True

        # Regression guard: a successful atomic write
        # must not leave SQLite inside a transaction.
        assert storage.connection.in_transaction is False

        book = OrderBook(
            token_id="123456",
            bids=(
                OrderBookLevel(
                    price=Decimal("0.45"),
                    size=Decimal("100"),
                ),
            ),
            asks=(
                OrderBookLevel(
                    price=Decimal("0.47"),
                    size=Decimal("80"),
                ),
            ),
        )

        book_inserted = storage.save_order_book(
            book=book,
            source_timestamp_ms=1793548801000,
            observed_at_utc="2026-11-01T16:00:01Z",
            book_hash="transaction-boundary-test",
            stream_session_id=session_id,
            message_sequence=2,
        )

        assert book_inserted is True
        assert storage.connection.in_transaction is False

        assert storage.count_market_price_changes() == 1
        assert storage.count_snapshots() == 1

        finish_stream_session(
            storage.connection,
            session_id,
            status="completed",
        )

        assert storage.connection.in_transaction is False
