
from datetime import datetime, timezone

from prediction_desk.discovery import (
    normalize_crypto_market,
    discover_targeted_markets,
)


NOW = datetime(
    2026, 10, 25,
    tzinfo=timezone.utc,
)


def make_event():
    return {
        "title": "Bitcoin Up or Down - October 25",
    }


def make_market(**overrides):
    market = {
        "id": "100",
        "question": "Will the price go up?",
        "conditionId": "0xabc",
        "active": True,
        "closed": False,
        "acceptingOrders": True,
        "enableOrderBook": True,
        "endDate": "2026-12-31T23:00:00Z",
        "outcomes": '["Up", "Down"]',
        "clobTokenIds": '["123", "456"]',
    }

    market.update(overrides)
    return market


def test_normalize_directional_market():
    result = normalize_crypto_market(
        make_event(),
        make_market(),
        now=NOW,
    )

    assert result is not None
    assert result.asset == "BTC"
    assert result.market_type == "directional"
    assert result.outcome_tokens == (
        ("Up", "123"),
        ("Down", "456"),
    )


def test_reject_closed_market():
    result = normalize_crypto_market(
        make_event(),
        make_market(closed=True),
        now=NOW,
    )

    assert result is None


def test_reject_expired_market():
    result = normalize_crypto_market(
        make_event(),
        make_market(
            endDate="2026-02-23T17:00:00Z"
        ),
        now=NOW,
    )

    assert result is None


def test_reject_nontradable_market():
    result = normalize_crypto_market(
        make_event(),
        make_market(acceptingOrders=False),
        now=NOW,
    )

    assert result is None


def test_reject_invalid_tokens():
    result = normalize_crypto_market(
        make_event(),
        make_market(
            clobTokenIds='["123", "invalid"]'
        ),
        now=NOW,
    )

    assert result is None


def test_reject_mismatched_outcomes():
    result = normalize_crypto_market(
        make_event(),
        make_market(
            outcomes='["Up"]'
        ),
        now=NOW,
    )

    assert result is None


def test_targeted_discovery_deduplicates():
    class FakeClient:
        def search_events(self, query, limit, page):
            return {
                "events": [
                    {
                        **make_event(),
                        "markets": [make_market()],
                    }
                ],
                "pagination": {"hasMore": False},
            }

    results = discover_targeted_markets(
        FakeClient(),
    )

    assert len(results) == 1
    assert results[0].market_id == "100"
