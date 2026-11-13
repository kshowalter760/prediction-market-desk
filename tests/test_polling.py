
from decimal import Decimal

import pytest

from prediction_desk.polling import run_spot_polling
from prediction_desk.spot import SpotAPIError, SpotTrade
from prediction_desk.storage import Storage


BASE = 1_800_000_000_000


def make_trade(trade_id):
    return SpotTrade(
        asset="BTC",
        trade_id=trade_id,
        timestamp_ms=BASE + trade_id * 1000,
        price_usd=Decimal("80000"),
        size=Decimal("0.01"),
    )


class FakeClient:
    def __init__(self):
        self.calls = 0

    def get_recent_trades(self, asset, limit=100):
        self.calls += 1
        return [
            make_trade(self.calls),
        ]


def test_runs_requested_number_of_cycles(tmp_path):
    client = FakeClient()
    sleeps = []

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        summary = run_spot_polling(
            client,
            storage,
            assets=("BTC",),
            max_cycles=3,
            sleep_fn=sleeps.append,
        )

        assert storage.count_spot_trades() == 3
        assert storage.count_spot_collection_runs() == 3

    assert summary.cycles_completed == 3
    assert client.calls == 3
    assert sleeps == [5.0, 5.0]


def test_aggregates_collection_totals(tmp_path):
    client = FakeClient()

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        summary = run_spot_polling(
            client,
            storage,
            assets=("BTC",),
            max_cycles=2,
            sleep_fn=lambda _: None,
        )

    assert summary.total_fetched == 2
    assert summary.total_inserted == 2
    assert summary.total_duplicates == 0


def test_cycle_callback_receives_results(tmp_path):
    client = FakeClient()
    received = []

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        run_spot_polling(
            client,
            storage,
            assets=("BTC",),
            max_cycles=2,
            sleep_fn=lambda _: None,
            on_cycle=lambda number, results: received.append(
                (number, results[0].status)
            ),
        )

    assert received == [
        (1, "success"),
        (2, "success"),
    ]


def test_keyboard_interrupt_stops_cleanly(tmp_path):
    client = FakeClient()

    def interrupt(_):
        raise KeyboardInterrupt

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        summary = run_spot_polling(
            client,
            storage,
            assets=("BTC",),
            max_cycles=5,
            sleep_fn=interrupt,
        )

    assert summary.cycles_completed == 1
    assert summary.stopped_early is True


def test_rejects_invalid_interval(tmp_path):
    client = FakeClient()

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        with pytest.raises(ValueError):
            run_spot_polling(
                client,
                storage,
                interval_seconds=0,
            )


def test_rejects_invalid_cycle_count(tmp_path):
    client = FakeClient()

    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        with pytest.raises(ValueError):
            run_spot_polling(
                client,
                storage,
                max_cycles=0,
            )
