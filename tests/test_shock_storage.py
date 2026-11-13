
import json
from decimal import Decimal

import pytest

from prediction_desk.discovery import TradableCryptoMarket
from prediction_desk.market_signals import MarketShock
from prediction_desk.signals import PriceShock
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


def make_event():
    shock = PriceShock(
        token_id="123",
        market_id="100",
        outcome_name="Up",
        previous_timestamp_ms=100000,
        current_timestamp_ms=120000,
        previous_midpoint=Decimal("0.675"),
        current_midpoint=Decimal("0.445"),
        change=Decimal("-0.230"),
    )

    return MarketShock(
        market_id="100",
        timestamp_ms=120000,
        magnitude=Decimal("0.230"),
        outcome_shocks=(shock,),
    )


def test_market_shock_table_created(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()
        assert storage.count_market_shocks() == 0


def test_save_market_shock(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()
        storage.save_market(make_market())

        inserted = storage.save_market_shock(
            make_event()
        )

        assert inserted is True
        assert storage.count_market_shocks() == 1


def test_duplicate_market_shock_ignored(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()
        storage.save_market(make_market())

        event = make_event()

        assert storage.save_market_shock(event) is True
        assert storage.save_market_shock(event) is False
        assert storage.count_market_shocks() == 1


def test_supporting_outcomes_preserved(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()
        storage.save_market(make_market())
        storage.save_market_shock(make_event())

        row = storage.connection.execute(
            """
            SELECT outcome_details_json
            FROM market_shocks
            """
        ).fetchone()

        details = json.loads(row[0])

        assert len(details) == 1
        assert details[0]["token_id"] == "123"
        assert details[0]["change"] == "-0.230"


def test_rejects_invalid_event(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        with pytest.raises(TypeError):
            storage.save_market_shock("invalid")
