
from dataclasses import dataclass
from threading import Barrier

import pytest

from prediction_desk.coordinator import (
    run_coordinated_session,
    validate_token_ids,
)


@dataclass(frozen=True)
class FakeResult:
    messages_received: int


def test_rejects_placeholder_token_ids():
    with pytest.raises(ValueError):
        validate_token_ids(["YOUR_UP_TOKEN"])


def test_rejects_duplicate_token_ids():
    with pytest.raises(ValueError):
        validate_token_ids(["123", "123"])


def test_coordinator_runs_both_collectors(tmp_path):
    barrier = Barrier(2, timeout=5)

    def coinbase_collector(**kwargs):
        barrier.wait()
        return FakeResult(messages_received=5)

    def polymarket_collector(**kwargs):
        barrier.wait()
        return FakeResult(messages_received=8)

    result = run_coordinated_session(
        database_path=tmp_path / "test.db",
        token_ids=["123", "456"],
        duration_seconds=1,
        coinbase_collector=coinbase_collector,
        polymarket_collector=polymarket_collector,
    )

    assert result.coinbase.status == "completed"
    assert result.polymarket.status == "completed"

    assert result.coinbase.result.messages_received == 5
    assert result.polymarket.result.messages_received == 8


def test_one_worker_failure_does_not_hide_other_result(tmp_path):
    def failed_coinbase(**kwargs):
        raise ConnectionError("Coinbase unavailable")

    def working_polymarket(**kwargs):
        return FakeResult(messages_received=4)

    result = run_coordinated_session(
        database_path=tmp_path / "test.db",
        token_ids=["123"],
        duration_seconds=1,
        coinbase_collector=failed_coinbase,
        polymarket_collector=working_polymarket,
    )

    assert result.coinbase.status == "failed"
    assert "Coinbase unavailable" in result.coinbase.error

    assert result.polymarket.status == "completed"
    assert result.polymarket.result.messages_received == 4
