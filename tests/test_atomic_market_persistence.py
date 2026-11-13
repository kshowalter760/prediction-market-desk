
import sqlite3
from decimal import Decimal

import pytest

from prediction_desk.market_persistence import (
    persist_market_event,
)
from prediction_desk.polymarket_stream import (
    MarketPriceChange,
)




def create_storage(tmp_path):
    from prediction_desk.storage import Storage

    storage = Storage(tmp_path / "atomic_test.db")
    storage.initialize()

    return storage




def test_atomic_price_change_saves_both_records(tmp_path):
    storage = create_storage(tmp_path)

    try:
        event = MarketPriceChange(
            token_id="123456",
            best_bid=Decimal("0.49"),
            best_ask=Decimal("0.50"),
            timestamp_ms=1000,
            price=Decimal("0.48"),
            size=Decimal("125"),
            side="BUY",
        )

        result = persist_market_event(storage, event)

        assert result.inserted is True

        quotes = storage.connection.execute(
            "SELECT COUNT(*) FROM market_price_changes"
        ).fetchone()[0]

        levels = storage.connection.execute(
            "SELECT COUNT(*) FROM market_level_updates"
        ).fetchone()[0]

        assert quotes == 1
        assert levels == 1

    finally:
        storage.connection.close()


def test_atomic_price_change_rolls_back_on_second_insert_failure(
        tmp_path,
):
    storage = create_storage(tmp_path)

    try:
        # Force the second insert to fail.
        storage.connection.execute(
            "DROP TABLE market_level_updates"
        )
        storage.connection.commit()

        event = MarketPriceChange(
            token_id="123456",
            best_bid=Decimal("0.49"),
            best_ask=Decimal("0.50"),
            timestamp_ms=1000,
            price=Decimal("0.48"),
            size=Decimal("125"),
            side="BUY",
        )

        with pytest.raises(sqlite3.OperationalError):
            persist_market_event(storage, event)

        quotes = storage.connection.execute(
            "SELECT COUNT(*) FROM market_price_changes"
        ).fetchone()[0]

        assert quotes == 0

    finally:
        storage.connection.close()


def test_atomic_price_change_without_level_information(tmp_path):
    storage = create_storage(tmp_path)

    try:
        event = MarketPriceChange(
            token_id="123456",
            best_bid=Decimal("0.49"),
            best_ask=Decimal("0.50"),
            timestamp_ms=1000,
        )

        persist_market_event(storage, event)

        quotes = storage.connection.execute(
            "SELECT COUNT(*) FROM market_price_changes"
        ).fetchone()[0]

        levels = storage.connection.execute(
            "SELECT COUNT(*) FROM market_level_updates"
        ).fetchone()[0]

        assert quotes == 1
        assert levels == 0

    finally:
        storage.connection.close()
