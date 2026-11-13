
from decimal import Decimal

from prediction_desk.spot import (
    SpotAPIError,
    SpotTrade,
)
from prediction_desk.spot_collector import (
    collect_spot_trades,
)
from prediction_desk.storage import Storage


BASE = 1_800_000_000_000


def make_trade(asset, trade_id, offset_ms):
    return SpotTrade(
        asset=asset,
        trade_id=trade_id,
        timestamp_ms=BASE + offset_ms,
        price_usd=Decimal("80000"),
        size=Decimal("0.01"),
    )


class FakeClient:
    def __init__(self, responses):
        self.responses = responses

    def get_recent_trades(self, asset, limit=100):
        response = self.responses[asset]

        if isinstance(response, Exception):
            raise response

        return response[:limit]


def test_collects_both_assets(tmp_path):
    client = FakeClient({
        "BTC": [
            make_trade("BTC", 1, 1000),
            make_trade("BTC", 2, 4000),
        ],
        "ETH": [
            make_trade("ETH", 1, 2000),
        ],
    })

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        results = collect_spot_trades(
            client,
            storage,
        )

        assert storage.count_spot_trades() == 3

    assert len(results) == 2
    assert results[0].inserted == 2
    assert results[1].inserted == 1
    assert results[0].coverage_seconds == 3.0


def test_repeated_collection_is_idempotent(tmp_path):
    client = FakeClient({
        "BTC": [
            make_trade("BTC", 1, 1000),
        ],
    })

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        first = collect_spot_trades(
            client,
            storage,
            assets=("BTC",),
        )

        second = collect_spot_trades(
            client,
            storage,
            assets=("BTC",),
        )

    assert first[0].inserted == 1
    assert second[0].inserted == 0
    assert second[0].duplicate_count == 1


def test_api_failure_is_isolated(tmp_path):
    client = FakeClient({
        "BTC": SpotAPIError("Unavailable"),
        "ETH": [
            make_trade("ETH", 1, 1000),
        ],
    })

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        results = collect_spot_trades(
            client,
            storage,
        )

        assert storage.count_spot_trades() == 1

    assert results[0].status == "api_error"
    assert results[1].status == "success"


def test_empty_response(tmp_path):
    client = FakeClient({
        "BTC": [],
    })

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        results = collect_spot_trades(
            client,
            storage,
            assets=("BTC",),
        )

    assert results[0].status == "empty_response"
    assert results[0].fetched == 0


def test_rejects_duplicate_assets(tmp_path):
    client = FakeClient({})

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        try:
            collect_spot_trades(
                client,
                storage,
                assets=("BTC", "BTC"),
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "Expected duplicate asset rejection"
            )


def test_rejects_invalid_limit(tmp_path):
    client = FakeClient({})

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        try:
            collect_spot_trades(
                client,
                storage,
                limit=0,
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "Expected invalid limit rejection"
            )
