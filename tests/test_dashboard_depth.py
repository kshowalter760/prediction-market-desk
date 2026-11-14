
import sqlite3

import pytest

from prediction_desk.dashboard_data import load_order_book_depth


@pytest.fixture
def depth_database(tmp_path):
    """Create an isolated SQLite database for depth tests."""

    database = tmp_path / "depth_test.db"

    with sqlite3.connect(database) as conn:
        conn.execute(
            """
            CREATE TABLE order_book_levels (
                id INTEGER PRIMARY KEY,
                snapshot_id INTEGER NOT NULL,
                side TEXT NOT NULL,
                price TEXT,
                size TEXT
            )
            """
        )

    return database


def insert_levels(database, snapshot_id, levels):
    """Insert price levels into the test database."""

    with sqlite3.connect(database) as conn:
        conn.executemany(
            """
            INSERT INTO order_book_levels (
                snapshot_id,
                side,
                price,
                size
            )
            VALUES (?, ?, ?, ?)
            """,
            [
                (snapshot_id, side, price, size)
                for side, price, size in levels
            ],
        )


def test_buy_levels_sorted_highest_first(depth_database):
    insert_levels(
        depth_database,
        1,
        [
            ("BUY", "0.40", "10"),
            ("BUY", "0.50", "20"),
            ("BUY", "0.45", "15"),
        ],
    )

    result = load_order_book_depth(depth_database, 1)

    assert result["price"].tolist() == [
        0.50, 0.45, 0.40
    ]


def test_sell_levels_sorted_lowest_first(depth_database):
    insert_levels(
        depth_database,
        1,
        [
            ("SELL", "0.60", "10"),
            ("SELL", "0.55", "20"),
            ("SELL", "0.65", "15"),
        ],
    )

    result = load_order_book_depth(depth_database, 1)

    assert result["price"].tolist() == [
        0.55, 0.60, 0.65
    ]


def test_buy_cumulative_depth(depth_database):
    insert_levels(
        depth_database,
        1,
        [
            ("BUY", "0.50", "10"),
            ("BUY", "0.45", "20"),
            ("BUY", "0.40", "30"),
        ],
    )

    result = load_order_book_depth(depth_database, 1)

    assert result["cumulative_size"].tolist() == [
        10.0, 30.0, 60.0
    ]


def test_sell_cumulative_depth(depth_database):
    insert_levels(
        depth_database,
        1,
        [
            ("SELL", "0.55", "5"),
            ("SELL", "0.60", "15"),
            ("SELL", "0.65", "25"),
        ],
    )

    result = load_order_book_depth(depth_database, 1)

    assert result["cumulative_size"].tolist() == [
        5.0, 20.0, 45.0
    ]


def test_both_sides_accumulate_independently(depth_database):
    insert_levels(
        depth_database,
        1,
        [
            ("BUY", "0.50", "10"),
            ("BUY", "0.45", "20"),
            ("SELL", "0.55", "5"),
            ("SELL", "0.60", "15"),
        ],
    )

    result = load_order_book_depth(depth_database, 1)

    bids = result[result["side"] == "BUY"]
    asks = result[result["side"] == "SELL"]

    assert bids["cumulative_size"].tolist() == [
        10.0, 30.0
    ]

    assert asks["cumulative_size"].tolist() == [
        5.0, 20.0
    ]


def test_one_sided_book(depth_database):
    insert_levels(
        depth_database,
        1,
        [
            ("BUY", "0.50", "10"),
            ("BUY", "0.45", "20"),
        ],
    )

    result = load_order_book_depth(depth_database, 1)

    assert len(result) == 2
    assert set(result["side"]) == {"BUY"}


def test_empty_snapshot(depth_database):
    result = load_order_book_depth(depth_database, 999)

    assert result.empty

    assert result.columns.tolist() == [
        "side",
        "price",
        "size",
        "cumulative_size",
    ]


@pytest.mark.parametrize(
    "snapshot_id",
    [
        0,
        -1,
        True,
        1.5,
        "1",
        None,
    ],
)
def test_invalid_snapshot_id(depth_database, snapshot_id):
    with pytest.raises(
        ValueError,
        match="snapshot_id must be a positive integer",
    ):
        load_order_book_depth(depth_database, snapshot_id)


@pytest.mark.parametrize(
    "invalid_level",
    [
        ("BUY", "-0.01", "10"),
        ("SELL", "1.01", "10"),
        ("BUY", "0.50", "0"),
        ("SELL", "0.50", "-5"),
        ("BUY", "invalid", "10"),
        ("SELL", "0.50", "invalid"),
        ("UNKNOWN", "0.50", "10"),
        ("BUY", None, "10"),
        ("SELL", "0.50", None),
    ],
)
def test_invalid_levels_rejected(
    depth_database,
    invalid_level,
):
    insert_levels(
        depth_database,
        1,
        [invalid_level],
    )

    with pytest.raises(
        ValueError,
        match="invalid order-book levels",
    ):
        load_order_book_depth(depth_database, 1)


def test_original_price_levels_preserved(depth_database):
    insert_levels(
        depth_database,
        1,
        [
            ("BUY", "0.500", "10.000"),
            ("SELL", "0.510", "20.000"),
        ],
    )

    load_order_book_depth(depth_database, 1)

    with sqlite3.connect(depth_database) as conn:
        rows = conn.execute(
            """
            SELECT price, size
            FROM order_book_levels
            ORDER BY id
            """
        ).fetchall()

    assert rows == [
        ("0.500", "10.000"),
        ("0.510", "20.000"),
    ]


@pytest.mark.parametrize(
    "invalid_level",
    [
        ("BUY", "NaN", "10"),
        ("SELL", "Infinity", "10"),
        ("BUY", "0.50", "NaN"),
        ("SELL", "0.50", "Infinity"),
        ("BUY", "0.50", "-Infinity"),
    ],
)
def test_nonfinite_values_rejected(
    depth_database,
    invalid_level,
):
    insert_levels(
        depth_database,
        1,
        [invalid_level],
    )

    with pytest.raises(
        ValueError,
        match="invalid order-book levels",
    ):
        load_order_book_depth(depth_database, 1)


def test_duplicate_price_levels_rejected(depth_database):
    insert_levels(
        depth_database,
        1,
        [
            ("BUY", "0.50", "10"),
            ("BUY", "0.50", "20"),
        ],
    )

    with pytest.raises(
        ValueError,
        match="duplicate price levels",
    ):
        load_order_book_depth(depth_database, 1)


def test_crossed_book_rejected(depth_database):
    insert_levels(
        depth_database,
        1,
        [
            ("BUY", "0.60", "10"),
            ("SELL", "0.55", "20"),
        ],
    )

    with pytest.raises(
        ValueError,
        match="crossed order book",
    ):
        load_order_book_depth(depth_database, 1)


def test_locked_book_is_not_crossed(depth_database):
    insert_levels(
        depth_database,
        1,
        [
            ("BUY", "0.50", "10"),
            ("SELL", "0.50", "20"),
        ],
    )

    result = load_order_book_depth(depth_database, 1)

    assert len(result) == 2
