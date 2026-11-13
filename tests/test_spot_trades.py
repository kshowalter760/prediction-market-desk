
from decimal import Decimal

import httpx
import pytest

from prediction_desk.spot import (
    CoinbaseSpotClient,
    SpotAPIError,
)


def make_trade(
    trade_id,
    time="2026-10-26T23:10:05Z",
    price="79730.50",
    size="0.01",
):
    return {
        "trade_id": trade_id,
        "time": time,
        "price": price,
        "size": size,
        "side": "buy",
    }


def test_parses_and_sorts_trades():
    def handler(request):
        assert request.url.path == (
            "/products/BTC-USD/trades"
        )
        assert request.url.params["limit"] == "10"

        return httpx.Response(
            200,
            json=[
                make_trade(
                    102,
                    "2026-10-26T23:10:06Z",
                    "79740",
                ),
                make_trade(
                    101,
                    "2026-10-26T23:10:05Z",
                    "79730",
                ),
            ],
        )

    with CoinbaseSpotClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        trades = client.get_recent_trades(
            "BTC", limit=10
        )

    assert len(trades) == 2
    assert trades[0].trade_id == 101
    assert trades[1].price_usd == Decimal("79740")
    assert trades[0].asset == "BTC"


def test_rejects_negative_trade_price():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=[make_trade(101, price="-10")],
        )
    )

    with CoinbaseSpotClient(transport=transport) as client:
        with pytest.raises(SpotAPIError):
            client.get_recent_trades("BTC")


def test_rejects_invalid_timestamp():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=[make_trade(101, time="not-a-date")],
        )
    )

    with CoinbaseSpotClient(transport=transport) as client:
        with pytest.raises(SpotAPIError):
            client.get_recent_trades("BTC")


def test_rejects_duplicate_trade_ids():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=[
                make_trade(101),
                make_trade(101),
            ],
        )
    )

    with CoinbaseSpotClient(transport=transport) as client:
        with pytest.raises(SpotAPIError):
            client.get_recent_trades("BTC")


def test_rejects_invalid_limit():
    with CoinbaseSpotClient() as client:
        with pytest.raises(ValueError):
            client.get_recent_trades(
                "BTC", limit=0
            )


def test_handles_http_failure():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(503)
    )

    with CoinbaseSpotClient(transport=transport) as client:
        with pytest.raises(SpotAPIError):
            client.get_recent_trades("ETH")
