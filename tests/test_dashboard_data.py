from pandas.errors import DatabaseError
import sqlite3

import pytest

from prediction_desk.dashboard_data import (
    count_rows,
    read_query,
)


@pytest.fixture
def dashboard_db(tmp_path):
    """Create an isolated SQLite database for dashboard tests."""

    database = tmp_path / "dashboard_test.db"

    with sqlite3.connect(database) as connection:
        connection.execute("""
            CREATE TABLE markets (
                market_id TEXT PRIMARY KEY,
                asset TEXT NOT NULL
            )
        """)

        connection.executemany(
            "INSERT INTO markets (market_id, asset) VALUES (?, ?)",
            [
                ("market_1", "BTC"),
                ("market_2", "ETH"),
            ],
        )

        connection.execute("""
            CREATE TABLE outcomes (
                token_id TEXT PRIMARY KEY
            )
        """)

        connection.execute(
            "INSERT INTO outcomes (token_id) VALUES (?)",
            ("token_1",),
        )

        connection.execute("""
            CREATE TABLE order_book_snapshots (
                id INTEGER PRIMARY KEY
            )
        """)

        connection.execute("""
            CREATE TABLE spot_trades (
                id INTEGER PRIMARY KEY
            )
        """)

        connection.commit()

    return database


def test_read_query_returns_expected_rows(dashboard_db):
    result = read_query(
        dashboard_db,
        "SELECT market_id, asset FROM markets ORDER BY market_id",
    )

    assert len(result) == 2
    assert result["asset"].tolist() == ["BTC", "ETH"]


def test_read_query_supports_parameters(dashboard_db):
    result = read_query(
        dashboard_db,
        "SELECT market_id FROM markets WHERE asset = ?",
        ("BTC",),
    )

    assert len(result) == 1
    assert result.iloc[0]["market_id"] == "market_1"


def test_count_rows_returns_correct_counts(dashboard_db):
    assert count_rows(dashboard_db, "markets") == 2
    assert count_rows(dashboard_db, "outcomes") == 1
    assert count_rows(dashboard_db, "order_book_snapshots") == 0
    assert count_rows(dashboard_db, "spot_trades") == 0


def test_count_rows_rejects_unsupported_tables(dashboard_db):
    with pytest.raises(ValueError, match="Unsupported table"):
        count_rows(dashboard_db, "sqlite_master")


def test_read_query_rejects_missing_database(tmp_path):
    missing_database = tmp_path / "missing.db"

    with pytest.raises(FileNotFoundError):
        read_query(missing_database, "SELECT 1")

    assert not missing_database.exists()



def test_read_query_prevents_database_writes(dashboard_db):
    with pytest.raises(
        DatabaseError,
        match="readonly database",
    ):
        read_query(
            dashboard_db,
            "INSERT INTO markets (market_id, asset) "
            "VALUES ('market_3', 'BTC')",
        )

    assert count_rows(dashboard_db, "markets") == 2
