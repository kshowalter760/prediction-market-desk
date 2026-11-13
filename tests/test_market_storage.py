
from prediction_desk.discovery import TradableCryptoMarket
from prediction_desk.storage import Storage


def make_market():
    return TradableCryptoMarket(
        market_id="6170136",
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


def test_market_registry_initialization(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        assert storage.count_markets() == 0
        assert storage.count_outcomes() == 0


def test_save_market_and_outcomes(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()
        storage.save_market(make_market())

        assert storage.count_markets() == 1
        assert storage.count_outcomes() == 2


def test_market_save_is_idempotent(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        storage.save_market(make_market())
        storage.save_market(make_market())

        assert storage.count_markets() == 1
        assert storage.count_outcomes() == 2


def test_outcomes_reference_correct_market(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()
        storage.save_market(make_market())

        rows = storage.connection.execute(
            """
            SELECT outcome_name, market_id
            FROM outcomes
            ORDER BY outcome_name
            """
        ).fetchall()

        assert rows == [
            ("Down", "6170136"),
            ("Up", "6170136"),
        ]
