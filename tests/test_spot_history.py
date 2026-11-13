
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import httpx
import pytest

from prediction_desk.spot import (
    CoinbaseSpotClient,
    SpotAPIError,
)


START = datetime(
    2026, 10, 26, 12, 0, tzinfo=timezone.utc
)
END = START + timedelta(minutes=3)


def test_historical_candles_are_sorted():
    timestamp = int(START.timestamp())

    def handler(request):
        assert request.url.path == (
            "/products/BTC-USD/candles"
        )

        return httpx.Response(
            200,
            json=[
                [timestamp + 60, 99, 110, 100, 105, 5],
                [timestamp, 95, 105, 98, 101, 8],
            ],
        )

    with CoinbaseSpotClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        candles = client.get_historical_candles(
            "BTC", START, END
        )

    assert len(candles) == 2
    assert candles[0].start_timestamp_s == timestamp
    assert candles[1].close_usd == Decimal("105")


def test_invalid_ohlc_is_rejected():
    timestamp = int(START.timestamp())

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=[
                [timestamp, 100, 110, 90, 105, 5]
            ],
        )
    )

    with CoinbaseSpotClient(transport=transport) as client:
        with pytest.raises(SpotAPIError):
            client.get_historical_candles(
                "ETH", START, END
            )


def test_rejects_naive_datetime():
    naive = datetime(2026, 10, 26, 12, 0)

    with CoinbaseSpotClient() as client:
        with pytest.raises(ValueError):
            client.get_historical_candles(
                "BTC", naive, END
            )


def test_rejects_excessive_window():
    with CoinbaseSpotClient() as client:
        with pytest.raises(ValueError):
            client.get_historical_candles(
                "BTC",
                START,
                START + timedelta(hours=6),
            )


def test_rejects_reverse_window():
    with CoinbaseSpotClient() as client:
        with pytest.raises(ValueError):
            client.get_historical_candles(
                "BTC", END, START
            )


def test_empty_candle_response():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json=[]
        )
    )

    with CoinbaseSpotClient(transport=transport) as client:
        candles = client.get_historical_candles(
            "BTC", START, END
        )

    assert candles == []
