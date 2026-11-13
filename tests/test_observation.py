
from prediction_desk.discovery import TradableCryptoMarket
from prediction_desk.observation import observe_markets
from prediction_desk.polymarket import PolymarketAPIError
from prediction_desk.storage import Storage


def make_market():
    return TradableCryptoMarket(
        market_id="100",
        event_title="Bitcoin Up or Down",
        question="Bitcoin Up or Down",
        asset="BTC",
        market_type="directional",
        condition_id="0xabc",
        end_date="2026-12-31T23:59:00Z",
        outcome_tokens=(
            ("Up", "123"),
            ("Down", "456"),
        ),
    )


class FakeClient:
    def __init__(self, failing_token=None):
        self.failing_token = failing_token

    def get_order_book(self, token_id):
        if token_id == self.failing_token:
            raise PolymarketAPIError("Simulated API failure")

        return {
            "asset_id": token_id,
            "timestamp": "1792982700000",
            "hash": f"hash-{token_id}",
            "bids": [
                {"price": "0.48", "size": "100"}
            ],
            "asks": [
                {"price": "0.52", "size": "100"}
            ],
        }


def test_observes_both_outcomes(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        result = observe_markets(
            FakeClient(),
            storage,
            [make_market()],
        )

        assert result.markets_processed == 1
        assert result.tokens_attempted == 2
        assert result.snapshots_inserted == 2
        assert result.snapshots_duplicate == 0
        assert result.failures == ()

        assert storage.count_markets() == 1
        assert storage.count_outcomes() == 2
        assert storage.count_snapshots() == 2


def test_duplicate_snapshots_not_reinserted(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        client = FakeClient()
        market = make_market()

        observe_markets(client, storage, [market])

        result = observe_markets(
            client,
            storage,
            [market],
        )

        assert result.snapshots_inserted == 0
        assert result.snapshots_duplicate == 2
        assert storage.count_snapshots() == 2


def test_one_failed_token_does_not_stop_batch(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        result = observe_markets(
            FakeClient(failing_token="123"),
            storage,
            [make_market()],
        )

        assert result.tokens_attempted == 2
        assert result.snapshots_inserted == 1
        assert len(result.failures) == 1
        assert storage.count_snapshots() == 1
