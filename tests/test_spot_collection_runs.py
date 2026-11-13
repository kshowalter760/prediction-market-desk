
import pytest

from prediction_desk.storage import Storage


@pytest.fixture
def storage(tmp_path):
    with Storage(tmp_path / "audit.db") as database:
        database.initialize()
        yield database


def save_example_run(storage, asset="BTC"):
    return storage.save_spot_collection_run(
        asset=asset,
        started_at_utc="2026-10-27T01:00:00+00:00",
        completed_at_utc="2026-10-27T01:00:01+00:00",
        status="success",
        fetched=100,
        inserted=80,
        first_trade_id=1000,
        last_trade_id=1099,
        first_trade_timestamp_ms=1800000000000,
        last_trade_timestamp_ms=1800000010000,
        overlap_count=20,
    )


def test_run_table_created(storage):
    assert storage.count_spot_collection_runs() == 0


def test_save_collection_run(storage):
    run_id = save_example_run(storage)

    assert isinstance(run_id, int)
    assert run_id > 0
    assert storage.count_spot_collection_runs() == 1


def test_retrieve_latest_run(storage):
    save_example_run(storage)

    latest = storage.get_latest_spot_collection_run(
        "BTC"
    )

    assert latest["fetched"] == 100
    assert latest["inserted"] == 80
    assert latest["overlap_count"] == 20
    assert latest["first_trade_id"] == 1000


def test_asset_isolation(storage):
    save_example_run(storage, "BTC")
    save_example_run(storage, "ETH")

    assert storage.count_spot_collection_runs("BTC") == 1
    assert storage.count_spot_collection_runs("ETH") == 1


def test_latest_run_selected(storage):
    save_example_run(storage)

    storage.save_spot_collection_run(
        asset="BTC",
        started_at_utc="2026-10-27T01:01:00+00:00",
        completed_at_utc="2026-10-27T01:01:01+00:00",
        status="success",
        fetched=50,
        inserted=50,
    )

    latest = storage.get_latest_spot_collection_run(
        "BTC"
    )

    assert latest["fetched"] == 50


def test_rejects_invalid_counts(storage):
    with pytest.raises(ValueError):
        storage.save_spot_collection_run(
            asset="BTC",
            started_at_utc="2026-10-27T01:00:00+00:00",
            completed_at_utc="2026-10-27T01:00:01+00:00",
            status="success",
            fetched=10,
            inserted=11,
        )
