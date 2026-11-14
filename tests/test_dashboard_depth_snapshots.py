import pandas as pd
import sqlite3

import pytest

from prediction_desk.dashboard_data import load_depth_snapshots


@pytest.fixture
def database(tmp_path):
    db = tmp_path / "depth_snapshots.db"

    with sqlite3.connect(db) as conn:
        conn.executescript("""
            CREATE TABLE markets (
                market_id TEXT PRIMARY KEY,
                asset TEXT,
                question TEXT
            );

            CREATE TABLE outcomes (
                token_id TEXT PRIMARY KEY,
                market_id TEXT,
                outcome_name TEXT
            );

            CREATE TABLE order_book_snapshots (
                id INTEGER PRIMARY KEY,
                token_id TEXT,
                observed_at_utc TEXT
            );

            CREATE TABLE order_book_levels (
                id INTEGER PRIMARY KEY,
                snapshot_id INTEGER,
                side TEXT,
                price TEXT,
                size TEXT
            );
        """)

    return db


def seed_data(database):
    with sqlite3.connect(database) as conn:
        conn.execute(
            """
            INSERT INTO markets VALUES (?, ?, ?)
            """,
            ("market-1", "BTC", "Will Bitcoin rise?"),
        )

        conn.execute(
            """
            INSERT INTO outcomes VALUES (?, ?, ?)
            """,
            ("token-a", "market-1", "Up"),
        )

        conn.executemany(
            """
            INSERT INTO order_book_snapshots
            VALUES (?, ?, ?)
            """,
            [
                (1, "token-a", "2026-11-14T12:00:00Z"),
                (2, "token-a", "2026-11-14T12:01:00Z"),
                (3, "orphan-token", "2026-11-14T12:02:00Z"),
            ],
        )

        conn.executemany(
            """
            INSERT INTO order_book_levels
            (snapshot_id, side, price, size)
            VALUES (?, ?, ?, ?)
            """,
            [
                (2, "BUY", "0.49", "10"),
                (2, "SELL", "0.51", "20"),
                (3, "BUY", "0.40", "15"),
            ],
        )


def test_only_snapshots_with_depth_returned(database):
    seed_data(database)

    result = load_depth_snapshots(database)

    assert set(result["snapshot_id"]) == {2, 3}
    assert 1 not in result["snapshot_id"].tolist()


def test_level_counts(database):
    seed_data(database)

    result = load_depth_snapshots(database)

    counts = dict(
        zip(result["snapshot_id"], result["level_count"])
    )

    assert counts == {2: 2, 3: 1}


def test_registered_market_metadata(database):
    seed_data(database)

    result = load_depth_snapshots(database)

    row = result.loc[
        result["snapshot_id"] == 2
    ].iloc[0]

    assert row["asset"] == "BTC"
    assert row["question"] == "Will Bitcoin rise?"
    assert row["outcome_name"] == "Up"



def test_unregistered_token_preserved(database):
    seed_data(database)

    result = load_depth_snapshots(database)

    row = result.loc[
        result["snapshot_id"] == 3
    ].iloc[0]

    assert row["token_id"] == "orphan-token"
    assert pd.isna(row["asset"])
    assert pd.isna(row["outcome_name"])



def test_newest_snapshot_first(database):
    seed_data(database)

    result = load_depth_snapshots(database)

    assert result["snapshot_id"].tolist() == [3, 2]


def test_empty_database(database):
    result = load_depth_snapshots(database)

    assert result.empty

    assert "snapshot_id" in result.columns
    assert "level_count" in result.columns


def test_snapshot_with_multiple_levels_not_duplicated(database):
    seed_data(database)

    result = load_depth_snapshots(database)

    assert len(result) == 2
    assert result["snapshot_id"].is_unique


def test_query_does_not_modify_database(database):
    seed_data(database)

    with sqlite3.connect(database) as conn:
        before = conn.execute(
            "SELECT COUNT(*) FROM order_book_levels"
        ).fetchone()[0]

    load_depth_snapshots(database)

    with sqlite3.connect(database) as conn:
        after = conn.execute(
            "SELECT COUNT(*) FROM order_book_levels"
        ).fetchone()[0]

    assert before == after
