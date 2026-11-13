
import pytest

from prediction_desk.discovery import (
    classify_market,
    discover_crypto_markets,
)


def make_market(
    market_id,
    question,
    active=True,
    closed=False,
):
    return {
        "id": str(market_id),
        "conditionId": f"condition-{market_id}",
        "question": question,
        "active": active,
        "closed": closed,
        "endDate": "2026-12-31T23:59:00Z",
    }


def test_classify_btc_price_market():
    market = make_market(
        1,
        "Will Bitcoin be above $100,000?",
    )

    result = classify_market(market)

    assert result is not None
    assert result.asset == "BTC"
    assert result.market_id == "1"


def test_classify_eth_price_market():
    market = make_market(
        2,
        "Will Ethereum price reach $5,000?",
    )

    result = classify_market(market)

    assert result is not None
    assert result.asset == "ETH"


def test_reject_non_price_market():
    market = make_market(
        3,
        "Will Bitcoin regulation pass?",
    )

    assert classify_market(market) is None


def test_reject_inactive_market():
    market = make_market(
        4,
        "Will BTC be above $100,000?",
        active=False,
    )

    assert classify_market(market) is None


def test_reject_closed_market():
    market = make_market(
        5,
        "Will ETH be below $2,000?",
        closed=True,
    )

    assert classify_market(market) is None


def test_reject_ambiguous_assets():
    market = make_market(
        6,
        "Will BTC price outperform ETH price?",
    )

    assert classify_market(market) is None


def test_discovery_pagination_and_deduplication():
    class FakeClient:
        def get_markets(self, limit, offset):
            pages = {
                0: [
                    make_market(
                        1,
                        "Will BTC be above $100,000?",
                    ),
                    make_market(
                        2,
                        "Will ETH be below $2,000?",
                    ),
                ],
                2: [
                    make_market(
                        1,
                        "Will BTC be above $100,000?",
                    ),
                    make_market(
                        3,
                        "Will Bitcoin regulation pass?",
                    ),
                ],
                4: [],
            }

            return pages.get(offset, [])

    results = discover_crypto_markets(
        client=FakeClient(),
        page_size=2,
        max_pages=5,
    )

    assert len(results) == 2
    assert {item.market_id for item in results} == {
        "1",
        "2",
    }


@pytest.mark.parametrize(
    "page_size,max_pages",
    [
        (0, 5),
        (501, 5),
        (100, 0),
        (True, 5),
        (100, False),
    ],
)
def test_invalid_discovery_settings(
    page_size,
    max_pages,
):
    with pytest.raises(ValueError):
        discover_crypto_markets(
            client=None,
            page_size=page_size,
            max_pages=max_pages,
        )
