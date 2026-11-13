
from datetime import datetime, timezone

import pytest

from prediction_desk.discovery import (
    discover_directional_markets,
)


NOW = datetime(
    2026, 10, 25, 22, 47,
    tzinfo=timezone.utc,
)


def make_event(slug):
    asset = "Bitcoin" if slug.startswith("btc") else "Ethereum"

    return {
        "title": f"{asset} Up or Down",
        "markets": [
            {
                "id": slug,
                "question": f"{asset} Up or Down",
                "conditionId": "0xabc",
                "active": True,
                "closed": False,
                "acceptingOrders": True,
                "enableOrderBook": True,
                "endDate": "2026-12-31T23:59:00Z",
                "outcomes": '["Up", "Down"]',
                "clobTokenIds": '["123", "456"]',
            }
        ],
    }


class FakeClient:
    def __init__(self):
        self.slugs = []

    def get_event_by_slug(self, slug):
        self.slugs.append(slug)
        return make_event(slug)


def test_discovers_btc_and_eth():
    client = FakeClient()

    results = discover_directional_markets(
        client,
        now=NOW,
        future_intervals=2,
    )

    assert len(results) == 6
    assert sum(m.asset == "BTC" for m in results) == 3
    assert sum(m.asset == "ETH" for m in results) == 3
    assert all(
        m.market_type == "directional"
        for m in results
    )


def test_correct_time_buckets():
    client = FakeClient()

    discover_directional_markets(
        client,
        now=NOW,
        future_intervals=1,
    )

    current_bucket = (
        int(NOW.timestamp()) // 900
    ) * 900

    assert client.slugs == [
        f"btc-updown-15m-{current_bucket}",
        f"btc-updown-15m-{current_bucket + 900}",
        f"eth-updown-15m-{current_bucket}",
        f"eth-updown-15m-{current_bucket + 900}",
    ]


def test_missing_events_are_skipped():
    class MissingClient:
        def get_event_by_slug(self, slug):
            return None

    results = discover_directional_markets(
        MissingClient(),
        now=NOW,
    )

    assert results == []


def test_rejects_naive_datetime():
    with pytest.raises(ValueError):
        discover_directional_markets(
            FakeClient(),
            now=datetime(2026, 10, 25),
        )


def test_rejects_negative_intervals():
    with pytest.raises(ValueError):
        discover_directional_markets(
            FakeClient(),
            now=NOW,
            future_intervals=-1,
        )
