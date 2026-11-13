
import sqlite3
from decimal import Decimal

import pytest

from prediction_desk.storage import Storage


def test_source_timestamp_is_persisted(tmp_path):
    database = tmp_path / "test.db"

    with Storage(str(database)) as storage:
        storage.initialize()

        inserted = storage.save_market_price_change(
            token_id="123456",
            best_bid=Decimal("0.50"),
            best_ask=Decimal("0.51"),
            observed_at_utc="2026-10-28T16:00:00+00:00",
            source_timestamp_ms=1793203200123,
        )

        assert inserted is True

        row = storage.connection.execute(
            """
            SELECT source_timestamp_ms, best_bid, best_ask
            FROM market_price_changes
            """
        ).fetchone()

        assert row[0] == 1793203200123
        assert row[1] == "0.50"
        assert row[2] == "0.51"


def test_missing_source_timestamp_is_supported(tmp_path):
    with Storage(str(tmp_path / "test.db")) as storage:
        storage.initialize()

        storage.save_market_price_change(
            token_id="123456",
            best_bid=Decimal("0.50"),
            best_ask=Decimal("0.51"),
            observed_at_utc="2026-10-28T16:00:00+00:00",
        )

        row = storage.connection.execute(
            """
            SELECT source_timestamp_ms
            FROM market_price_changes
            """
        ).fetchone()

        assert row[0] is None


def test_migration_preserves_existing_rows(tmp_path):
    database = tmp_path / "legacy.db"

    connection = sqlite3.connect(database)

    connection.execute(
        """
        CREATE TABLE market_price_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_id TEXT NOT NULL,
            observed_at_utc TEXT NOT NULL,
            best_bid TEXT,
            best_ask TEXT
        )
        """
    )

    connection.execute(
        """
        INSERT INTO market_price_changes (
            token_id,
            observed_at_utc,
            best_bid,
            best_ask
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            "123456",
            "2026-10-28T16:00:00+00:00",
            "0.50",
            "0.51",
        ),
    )

    connection.commit()
    connection.close()

    with Storage(str(database)) as storage:
        storage.initialize()

        row = storage.connection.execute(
            """
            SELECT token_id, source_timestamp_ms
            FROM market_price_changes
            """
        ).fetchone()

        assert row[0] == "123456"
        assert row[1] is None

        storage.initialize()

        assert storage.count_market_price_changes() == 1


def test_invalid_source_timestamp_rejected(tmp_path):
    with Storage(str(tmp_path / "test.db")) as storage:
        storage.initialize()

        with pytest.raises(ValueError):
            storage.save_market_price_change(
                token_id="123456",
                best_bid=Decimal("0.50"),
                best_ask=Decimal("0.51"),
                observed_at_utc="2026-10-28T16:00:00+00:00",
                source_timestamp_ms=-1,
            )
