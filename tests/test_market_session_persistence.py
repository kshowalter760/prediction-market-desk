
from decimal import Decimal

from prediction_desk.storage import Storage
from prediction_desk.market_persistence import persist_market_event
from prediction_desk.polymarket_stream import MarketPriceChange
from prediction_desk.stream_sessions import (
    start_stream_session,
    finish_stream_session,
)


def test_market_change_persists_session_metadata(tmp_path):
    database_path = tmp_path / "session_test.db"

    with Storage(database_path) as storage:
        storage.initialize()

        session_id = start_stream_session(storage.connection)

        event = MarketPriceChange(
            token_id="123456",
            best_bid=Decimal("0.45"),
            best_ask=Decimal("0.46"),
            timestamp_ms=1793471105829,
            price=Decimal("0.45"),
            size=Decimal("100"),
            side="BUY",
        )

        result = persist_market_event(
            storage,
            event,
            stream_session_id=session_id,
            message_sequence=1,
        )

        assert result.inserted is True

        price_change = storage.connection.execute(
            """
            SELECT
                stream_session_id,
                message_sequence,
                best_bid,
                best_ask
            FROM market_price_changes
            """
        ).fetchone()

        assert price_change == (
            session_id,
            1,
            "0.45",
            "0.46",
        )

        level_update = storage.connection.execute(
            """
            SELECT
                stream_session_id,
                message_sequence,
                price,
                size,
                side
            FROM market_level_updates
            """
        ).fetchone()

        assert level_update == (
            session_id,
            1,
            "0.45",
            "100",
            "BUY",
        )

        finish_stream_session(
            storage.connection,
            session_id,
            status="completed",
        )
