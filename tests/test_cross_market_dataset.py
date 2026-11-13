
import sqlite3

import pytest

from prediction_desk.cross_market_dataset import (
    build_cross_market_dataset,
    calculate_midpoint,
)
from prediction_desk.storage import Storage


def seed_database(path, event_timestamp_ms):
    with Storage(path) as storage:
        storage.initialize()

    connection = sqlite3.connect(path)

    try:
        connection.execute(
            """
            INSERT INTO markets (
                market_id, event_title, question,
                asset, market_type, condition_id, end_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "market-1", "BTC test", "BTC Up?",
                "BTC", "directional", "condition-1",
                "2026-10-28T12:15:00Z",
            ),
        )

        connection.execute(
            """
            INSERT INTO outcomes (
                token_id, market_id, outcome_name
            )
            VALUES (?, ?, ?)
            """,
            ("123", "market-1", "Up"),
        )

        connection.execute(
            """
            INSERT INTO spot_trades (
                asset, trade_id, trade_timestamp_ms,
                price_usd, size, observed_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "BTC", 101, 1000, "80000.00", "0.01",
                "2026-10-28T12:00:00+00:00",
            ),
        )

        connection.execute(
            """
            INSERT INTO order_book_snapshots (
                token_id, source_timestamp_ms,
                observed_at_utc, best_bid, best_ask,
                spread, book_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "123", event_timestamp_ms,
                "2026-10-28T12:00:01+00:00",
                "0.49", "0.51", "0.02", "hash-1",
            ),
        )

        connection.commit()

    finally:
        connection.close()


def test_midpoint():
    assert str(
        calculate_midpoint("0.49", "0.51")
    ) == "0.50"


def test_invalid_midpoint():
    assert calculate_midpoint("0.60", "0.50") is None


@pytest.mark.parametrize(
    ("event_time", "expected_status"),
    [
        (1500, "matched"),
        (8000, "stale_spot"),
        (500, "no_prior_spot"),
    ],
)
def test_alignment_status(
    tmp_path,
    event_time,
    expected_status,
):
    database = tmp_path / "test.db"
    seed_database(database, event_time)

    with sqlite3.connect(database) as connection:
        rows = build_cross_market_dataset(
            connection,
            max_age_ms=5000,
        )

    assert len(rows) == 1
    assert rows[0].status == expected_status


def test_matched_spot_price(tmp_path):
    database = tmp_path / "test.db"
    seed_database(database, 1500)

    with sqlite3.connect(database) as connection:
        rows = build_cross_market_dataset(
            connection,
            max_age_ms=5000,
        )

    row = rows[0]

    assert str(row.spot_price_usd) == "80000.00"
    assert row.spot_age_ms == 500
    assert row.spot_trade_id == 101


def test_rejects_invalid_age(tmp_path):
    database = tmp_path / "test.db"
    seed_database(database, 1500)

    with sqlite3.connect(database) as connection:
        with pytest.raises(ValueError):
            build_cross_market_dataset(
                connection,
                max_age_ms=-1,
            )
