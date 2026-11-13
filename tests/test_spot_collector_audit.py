
from decimal import Decimal

from prediction_desk.spot import SpotAPIError, SpotTrade
from prediction_desk.spot_collector import collect_spot_trades
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


def test_success_creates_audit_record(tmp_path):
    client = FakeClient({
        "BTC": [
            make_trade("BTC", 101, 1000),
            make_trade("BTC", 102, 3000),
        ]
    })

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        collect_spot_trades(
            client, storage, assets=("BTC",)
        )

        run = storage.get_latest_spot_collection_run("BTC")

        assert run["status"] == "success"
        assert run["fetched"] == 2
        assert run["inserted"] == 2
        assert run["first_trade_id"] == 101
        assert run["last_trade_id"] == 102
        assert run["started_at_utc"]
        assert run["completed_at_utc"]


def test_duplicate_collection_is_audited(tmp_path):
    client = FakeClient({
        "BTC": [make_trade("BTC", 101, 1000)]
    })

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        collect_spot_trades(
            client, storage, assets=("BTC",)
        )
        collect_spot_trades(
            client, storage, assets=("BTC",)
        )

        run = storage.get_latest_spot_collection_run("BTC")

        assert run["fetched"] == 1
        assert run["inserted"] == 0
        assert run["overlap_count"] == 1
        assert storage.count_spot_trades() == 1
        assert storage.count_spot_collection_runs() == 2


def test_api_error_creates_audit_record(tmp_path):
    client = FakeClient({
        "BTC": SpotAPIError("Unavailable")
    })

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        results = collect_spot_trades(
            client, storage, assets=("BTC",)
        )

        run = storage.get_latest_spot_collection_run("BTC")

        assert results[0].status == "api_error"
        assert run["status"] == "api_error"
        assert run["fetched"] == 0


def test_empty_response_creates_audit_record(tmp_path):
    client = FakeClient({"BTC": []})

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        collect_spot_trades(
            client, storage, assets=("BTC",)
        )

        run = storage.get_latest_spot_collection_run("BTC")

        assert run["status"] == "empty_response"
        assert run["inserted"] == 0


def test_both_assets_have_separate_audits(tmp_path):
    client = FakeClient({
        "BTC": [make_trade("BTC", 1, 1000)],
        "ETH": [make_trade("ETH", 1, 2000)],
    })

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        collect_spot_trades(client, storage)

        assert storage.count_spot_collection_runs("BTC") == 1
        assert storage.count_spot_collection_runs("ETH") == 1


def test_new_trades_in_second_collection(tmp_path):
    client = FakeClient({
        "BTC": [make_trade("BTC", 1, 1000)]
    })

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        collect_spot_trades(
            client, storage, assets=("BTC",)
        )

        client.responses["BTC"] = [
            make_trade("BTC", 1, 1000),
            make_trade("BTC", 2, 2000),
        ]

        collect_spot_trades(
            client, storage, assets=("BTC",)
        )

        run = storage.get_latest_spot_collection_run("BTC")

        assert run["fetched"] == 2
        assert run["inserted"] == 1
        assert run["overlap_count"] == 1
        assert storage.count_spot_trades() == 2
