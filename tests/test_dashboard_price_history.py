
import sqlite3

import pandas as pd
import pytest

from prediction_desk.dashboard_data import load_price_history


@pytest.fixture
def price_history_db(tmp_path):
    database = tmp_path / "price_history.db"

    with sqlite3.connect(database) as connection:
        connection.execute("""
            CREATE TABLE order_book_snapshots (
                id INTEGER PRIMARY KEY,
                token_id TEXT NOT NULL,
                observed_at_utc TEXT NOT NULL,
                best_bid TEXT,
                best_ask TEXT,
                spread TEXT
            )
        """)

        connection.executemany(
            """
            INSERT INTO order_book_snapshots (
                token_id,
                observed_at_utc,
                best_bid,
                best_ask,
                spread
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    "token_A",
                    "2026-11-01T10:00:00Z",
                    "0.40",
                    "0.44",
                    "0.04",
                ),
                (
                    "token_B",
                    "2026-11-01T10:01:00Z",
                    "0.60",
                    "0.64",
                    "0.04",
                ),
                (
                    "token_A",
                    "2026-11-01T10:02:00Z",
                    "0.42",
                    "0.46",
                    "0.04",
                ),
                (
                    "token_A",
                    "2026-11-01T10:03:00Z",
                    None,
                    "0.48",
                    None,
                ),
            ],
        )

        connection.commit()

    return database


def test_load_price_history_filters_by_token(price_history_db):
    result = load_price_history(price_history_db, "token_A")

    assert len(result) == 3
    assert result["best_ask"].tolist() == [
        0.44,
        0.46,
        0.48,
    ]


def test_load_price_history_respects_limit(price_history_db):
    result = load_price_history(
        price_history_db,
        "token_A",
        limit=2,
    )

    assert len(result) == 2
    assert result["best_ask"].tolist() == [0.46, 0.48]


def test_load_price_history_converts_timestamps(price_history_db):
    result = load_price_history(price_history_db, "token_A")

    assert isinstance(
        result.iloc[0]["observed_at_utc"],
        pd.Timestamp,
    )
    assert str(result["observed_at_utc"].dt.tz) == "UTC"


def test_load_price_history_preserves_missing_quotes(price_history_db):
    result = load_price_history(price_history_db, "token_A")

    assert pd.isna(result.iloc[-1]["best_bid"])
    assert pd.isna(result.iloc[-1]["spread"])


def test_load_price_history_returns_empty_for_unknown_token(
    price_history_db,
):
    result = load_price_history(
        price_history_db,
        "unknown_token",
    )

    assert result.empty


@pytest.mark.parametrize(
    "token_id",
    ["", "   ", None, 123],
)
def test_load_price_history_rejects_invalid_token(
    price_history_db,
    token_id,
):
    with pytest.raises(ValueError):
        load_price_history(price_history_db, token_id)


@pytest.mark.parametrize(
    "limit",
    [0, -1, 1.5, True, "100"],
)
def test_load_price_history_rejects_invalid_limit(
    price_history_db,
    limit,
):
    with pytest.raises(ValueError):
        load_price_history(
            price_history_db,
            "token_A",
            limit=limit,
        )
