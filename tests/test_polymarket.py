
import httpx
import pytest

from prediction_desk.polymarket import (
    PolymarketAPIError,
    PolymarketClient,
)


def test_get_markets():
    def handler(request):
        assert request.url.path == "/markets"
        assert request.url.params["limit"] == "5"

        return httpx.Response(
            200,
            json=[{"id": "123", "question": "BTC above 100k?"}],
        )

    transport = httpx.MockTransport(handler)

    with PolymarketClient(transport=transport) as client:
        markets = client.get_markets(limit=5)

    assert len(markets) == 1
    assert markets[0]["id"] == "123"


def test_get_order_book():
    def handler(request):
        assert request.url.path == "/book"
        assert request.url.params["token_id"] == "123"

        return httpx.Response(
            200,
            json={
                "asset_id": "123",
                "bids": [],
                "asks": [],
            },
        )

    transport = httpx.MockTransport(handler)

    with PolymarketClient(transport=transport) as client:
        book = client.get_order_book("123")

    assert book["asset_id"] == "123"


def test_invalid_token_id():
    with PolymarketClient() as client:
        with pytest.raises(ValueError):
            client.get_order_book("invalid")


def test_order_book_token_mismatch():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "asset_id": "999",
                "bids": [],
                "asks": [],
            },
        )
    )

    with PolymarketClient(transport=transport) as client:
        with pytest.raises(
            PolymarketAPIError,
            match="token ID mismatch",
        ):
            client.get_order_book("123")


def test_http_404_not_retried():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    with PolymarketClient(
        transport=transport,
        max_retries=2,
        retry_delay_seconds=0,
    ) as client:
        with pytest.raises(PolymarketAPIError):
            client.get_markets()

    assert attempts == 1


def test_http_503_retried():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1

        if attempts < 3:
            return httpx.Response(503)

        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)

    with PolymarketClient(
        transport=transport,
        max_retries=2,
        retry_delay_seconds=0,
    ) as client:
        markets = client.get_markets()

    assert markets == []
    assert attempts == 3
