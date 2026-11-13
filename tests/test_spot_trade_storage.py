
from decimal import Decimal

import pytest

from prediction_desk.spot import SpotTrade
from prediction_desk.storage import Storage


BASE = 1_800_000_000_000


def make_trade(
    trade_id,
    offset_ms=0,
    asset="BTC",
    price="80000.50",
):
    return SpotTrade(
        asset=asset,
        trade_id=trade_id,
        timestamp_ms=BASE + offset_ms,
        price_usd=Decimal(price),
        size=Decimal("0.015"),
    )


@pytest.fixture
def storage(tmp_path):
    with Storage(
        tmp_path / "research.db"
    ) as database:
        database.initialize()
        yield database


def test_spot_trade_table_created(storage):
    assert storage.count_spot_trades() == 0


def test_save_single_trade(storage):
    inserted = storage.save_spot_trades([
        make_trade(101),
    ])

    assert inserted == 1
    assert storage.count_spot_trades() == 1


def test_duplicate_trade_ignored(storage):
    trade = make_trade(101)

    assert storage.save_spot_trades([trade]) == 1
    assert storage.save_spot_trades([trade]) == 0

    assert storage.count_spot_trades() == 1


def test_same_trade_id_different_assets(storage):
    trades = [
        make_trade(101, asset="BTC"),
        make_trade(101, asset="ETH"),
    ]

    assert storage.save_spot_trades(trades) == 2

    assert storage.count_spot_trades("BTC") == 1
    assert storage.count_spot_trades("ETH") == 1


def test_retrieve_trades_by_time_window(storage):
    storage.save_spot_trades([
        make_trade(101, offset_ms=1000),
        make_trade(102, offset_ms=2000),
        make_trade(103, offset_ms=3000),
    ])

    rows = storage.get_spot_trades(
        asset="BTC",
        start_timestamp_ms=BASE + 1500,
        end_timestamp_ms=BASE + 2500,
    )

    assert len(rows) == 1
    assert rows[0]["trade_id"] == 102
    assert rows[0]["price_usd"] == "80000.50"
    assert rows[0]["observed_at_utc"]


def test_retrieval_is_chronological(storage):
    storage.save_spot_trades([
        make_trade(103, offset_ms=3000),
        make_trade(101, offset_ms=1000),
        make_trade(102, offset_ms=2000),
    ])

    rows = storage.get_spot_trades(
        "BTC",
        BASE,
        BASE + 5000,
    )

    assert [
        row["trade_id"]
        for row in rows
    ] == [101, 102, 103]


def test_rejects_invalid_time_window(storage):
    with pytest.raises(ValueError):
        storage.get_spot_trades(
            "BTC",
            BASE + 5000,
            BASE + 1000,
        )
