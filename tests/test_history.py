
import pytest

from prediction_desk.discovery import TradableCryptoMarket
from prediction_desk.models import OrderBook
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


def make_book(token_id):
    return OrderBook.from_api({
        "asset_id": token_id,
        "bids": [{"price": "0.48", "size": "100"}],
        "asks": [{"price": "0.52", "size": "100"}],
    })


def test_outcome_history_returns_joined_records(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()
        storage.save_market(make_market())

        storage.save_order_book(
            book=make_book("123"),
            source_timestamp_ms=1000,
            observed_at_utc="2026-10-26T00:00:00Z",
            book_hash="hash-1",
        )

        history = storage.get_outcome_history("123")

        assert len(history) == 1
        assert history[0]["market_id"] == "100"
        assert history[0]["outcome_name"] == "Up"
        assert history[0]["best_bid"] == "0.48"
        assert history[0]["best_ask"] == "0.52"


def test_history_is_newest_first(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()
        storage.save_market(make_market())

        for timestamp in (1000, 3000, 2000):
            storage.save_order_book(
                book=make_book("123"),
                source_timestamp_ms=timestamp,
                observed_at_utc="2026-10-26T00:00:00Z",
                book_hash=f"hash-{timestamp}",
            )

        history = storage.get_outcome_history("123")

        assert [
            row["source_timestamp_ms"]
            for row in history
        ] == [3000, 2000, 1000]


def test_history_limit(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()
        storage.save_market(make_market())

        for timestamp in (1000, 2000, 3000):
            storage.save_order_book(
                book=make_book("123"),
                source_timestamp_ms=timestamp,
                observed_at_utc="2026-10-26T00:00:00Z",
                book_hash=f"hash-{timestamp}",
            )

        assert len(
            storage.get_outcome_history("123", limit=2)
        ) == 2


@pytest.mark.parametrize(
    "token_id,limit",
    [
        ("abc", 10),
        ("123", 0),
        ("123", -1),
        ("123", True),
    ],
)
def test_invalid_history_arguments(tmp_path, token_id, limit):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        with pytest.raises(ValueError):
            storage.get_outcome_history(
                token_id,
                limit=limit,
            )
