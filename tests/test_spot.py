
import httpx
import pytest

from decimal import Decimal

from prediction_desk.spot import (
    CoinbaseSpotClient,
    SpotAPIError,
)


def test_btc_spot_quote():
    def handler(request):
        assert request.url.path == (
            "/products/BTC-USD/ticker"
        )

        return httpx.Response(
            200,
            json={"price": "68000.25"},
        )

    transport = httpx.MockTransport(handler)

    with CoinbaseSpotClient(transport=transport) as client:
        quote = client.get_spot_quote("BTC")

    assert quote.asset == "BTC"
    assert quote.product_id == "BTC-USD"
    assert quote.price_usd == Decimal("68000.25")


def test_eth_spot_quote():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"price": "3500.50"},
        )
    )

    with CoinbaseSpotClient(transport=transport) as client:
        quote = client.get_spot_quote("eth")

    assert quote.price_usd == Decimal("3500.50")


def test_rejects_unsupported_asset():
    with CoinbaseSpotClient() as client:
        with pytest.raises(ValueError):
            client.get_spot_quote("SOL")


def test_rejects_invalid_price():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"price": "-100"},
        )
    )

    with CoinbaseSpotClient(transport=transport) as client:
        with pytest.raises(SpotAPIError):
            client.get_spot_quote("BTC")


def test_handles_http_error():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(503)
    )

    with CoinbaseSpotClient(transport=transport) as client:
        with pytest.raises(SpotAPIError):
            client.get_spot_quote("ETH")


def test_rejects_missing_price():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"volume": "100"},
        )
    )

    with CoinbaseSpotClient(transport=transport) as client:
        with pytest.raises(SpotAPIError):
            client.get_spot_quote("BTC")
