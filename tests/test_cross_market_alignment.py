
import sqlite3
from decimal import Decimal

import pytest

from prediction_desk.book_reconstruction import BookReconstructor
from prediction_desk.replay_checkpoints import ReplayCheckpoint
from prediction_desk.cross_market_alignment import (
    find_latest_spot_trade,
    align_checkpoint,
    align_checkpoints,
)


D = Decimal


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")

    connection.execute(
        """
        CREATE TABLE spot_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset TEXT NOT NULL,
            trade_id INTEGER NOT NULL,
            trade_timestamp_ms INTEGER NOT NULL,
            price_usd TEXT NOT NULL,
            size TEXT NOT NULL,
            observed_at_utc TEXT NOT NULL,
            UNIQUE (asset, trade_id)
        )
        """
    )

    yield connection
    connection.close()


def add_trade(
    db,
    trade_id,
    timestamp_ms,
    price="78000.25",
    asset="BTC",
    size="0.125",
):
    db.execute(
        """
        INSERT INTO spot_trades (
            asset,
            trade_id,
            trade_timestamp_ms,
            price_usd,
            size,
            observed_at_utc
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            asset,
            trade_id,
            timestamp_ms,
            price,
            size,
            "2026-11-02T00:00:00+00:00",
        ),
    )


def make_checkpoint(timestamp_ms=10000):
    book = BookReconstructor(
        timestamp_ms=timestamp_ms,
        bids=[(D("0.49"), D("100"))],
        asks=[(D("0.51"), D("100"))],
    ).state()

    return ReplayCheckpoint(
        token_id="123",
        session_id=5,
        message_sequence=10,
        timestamp_ms=timestamp_ms,
        updates_applied=5,
        book=book,
    )


def test_exact_timestamp_alignment(db):
    add_trade(db, 1, 10000)

    result = align_checkpoint(db, make_checkpoint())

    assert result.alignment_status == "aligned"
    assert result.spot_age_ms == 0
    assert result.spot_trade_id == 1


def test_latest_eligible_trade_selected(db):
    add_trade(db, 1, 9000)
    add_trade(db, 2, 9800)
    add_trade(db, 3, 11000)

    result = align_checkpoint(db, make_checkpoint())

    assert result.spot_trade_id == 2
    assert result.spot_age_ms == 200


def test_future_trade_excluded(db):
    add_trade(db, 1, 10001)

    result = align_checkpoint(db, make_checkpoint())

    assert result.alignment_status == "missing_spot"
    assert result.spot_price_usd is None


def test_stale_trade_detected(db):
    add_trade(db, 1, 4000)

    result = align_checkpoint(
        db,
        make_checkpoint(),
        max_spot_age_ms=5000,
    )

    assert result.alignment_status == "stale_spot"
    assert result.spot_age_ms == 6000


def test_age_threshold_inclusive(db):
    add_trade(db, 1, 5000)

    result = align_checkpoint(
        db,
        make_checkpoint(),
        max_spot_age_ms=5000,
    )

    assert result.alignment_status == "aligned"
    assert result.spot_age_ms == 5000


def test_missing_spot_trade(db):
    result = align_checkpoint(db, make_checkpoint())

    assert result.alignment_status == "missing_spot"
    assert result.spot_trade_id is None
    assert result.spot_age_ms is None


def test_asset_filtering(db):
    add_trade(db, 1, 9900, asset="ETH")
    add_trade(db, 2, 9800, asset="BTC")

    result = align_checkpoint(
        db,
        make_checkpoint(),
        asset="BTC",
    )

    assert result.spot_trade_id == 2
    assert result.spot_age_ms == 200


def test_decimal_precision(db):
    add_trade(
        db,
        1,
        10000,
        price="78052.12345678",
        size="0.00000001",
    )

    spot = find_latest_spot_trade(
        db,
        asset="BTC",
        timestamp_ms=10000,
    )

    assert spot.price_usd == D("78052.12345678")
    assert spot.size == D("0.00000001")
    assert isinstance(spot.price_usd, Decimal)


def test_midpoint_and_spread(db):
    add_trade(db, 1, 10000)

    result = align_checkpoint(db, make_checkpoint())

    assert result.polymarket_mid_price == D("0.50")
    assert result.polymarket_spread == D("0.02")
    assert result.polymarket_imbalance == D("0")


def test_multiple_checkpoint_alignment(db):
    add_trade(db, 1, 9000)
    add_trade(db, 2, 19000)

    checkpoints = [
        make_checkpoint(10000),
        make_checkpoint(20000),
    ]

    results = align_checkpoints(
        db,
        checkpoints,
        max_spot_age_ms=5000,
    )

    assert len(results) == 2
    assert [r.spot_trade_id for r in results] == [1, 2]
    assert all(
        r.alignment_status == "aligned"
        for r in results
    )


def test_invalid_age_threshold(db):
    with pytest.raises(
        ValueError,
        match="Invalid maximum spot age",
    ):
        align_checkpoint(
            db,
            make_checkpoint(),
            max_spot_age_ms=-1,
        )


def test_invalid_lookup_timestamp(db):
    with pytest.raises(
        ValueError,
        match="Invalid timestamp",
    ):
        find_latest_spot_trade(
            db,
            asset="BTC",
            timestamp_ms=0,
        )
