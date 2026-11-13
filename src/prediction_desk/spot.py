
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation

import httpx


BASE_URL = "https://api.exchange.coinbase.com"


class SpotAPIError(Exception):
    pass


# ============================================================
# DATA MODELS
# ============================================================

@dataclass(frozen=True)
class SpotQuote:
    asset: str
    product_id: str
    price_usd: Decimal


@dataclass(frozen=True)
class SpotCandle:
    asset: str
    start_timestamp_s: int
    open_usd: Decimal
    high_usd: Decimal
    low_usd: Decimal
    close_usd: Decimal
    volume: Decimal

    @classmethod
    def from_api(cls, asset, data):
        if not isinstance(data, (list, tuple)) or len(data) != 6:
            raise ValueError("Invalid candle structure")

        try:
            timestamp = data[0]

            if (
                isinstance(timestamp, bool)
                or not isinstance(timestamp, int)
            ):
                raise ValueError("Invalid candle timestamp")

            low, high, opening, closing, volume = (
                Decimal(str(value))
                for value in data[1:]
            )

        except (
            TypeError,
            InvalidOperation,
            ValueError,
        ) as exc:
            raise ValueError("Invalid candle values") from exc

        prices = (low, high, opening, closing)

        if timestamp <= 0:
            raise ValueError("Invalid candle timestamp")

        if not all(
            price.is_finite() and price > 0
            for price in prices
        ):
            raise ValueError("Invalid candle prices")

        if not (
            low <= opening <= high
            and low <= closing <= high
        ):
            raise ValueError("Inconsistent OHLC prices")

        if not volume.is_finite() or volume < 0:
            raise ValueError("Invalid candle volume")

        return cls(
            asset=asset,
            start_timestamp_s=timestamp,
            open_usd=opening,
            high_usd=high,
            low_usd=low,
            close_usd=closing,
            volume=volume,
        )


@dataclass(frozen=True)
class SpotTrade:
    asset: str
    trade_id: int
    timestamp_ms: int
    price_usd: Decimal
    size: Decimal

    @classmethod
    def from_api(cls, asset, data):
        if not isinstance(data, dict):
            raise ValueError("Invalid trade structure")

        try:
            trade_id = data["trade_id"]
            timestamp_text = data["time"]
            price = Decimal(str(data["price"]))
            size = Decimal(str(data["size"]))

            if (
                not isinstance(trade_id, int)
                or isinstance(trade_id, bool)
                or trade_id <= 0
            ):
                raise ValueError("Invalid trade ID")

            if not isinstance(timestamp_text, str):
                raise ValueError("Invalid trade timestamp")

            trade_time = datetime.fromisoformat(
                timestamp_text.replace("Z", "+00:00")
            )

            if trade_time.tzinfo is None:
                raise ValueError(
                    "Trade timestamp must be timezone-aware"
                )

            timestamp_ms = int(
                trade_time.astimezone(
                    timezone.utc
                ).timestamp() * 1000
            )

        except (
            KeyError,
            TypeError,
            InvalidOperation,
            ValueError,
            OverflowError,
        ) as exc:
            raise ValueError("Invalid trade data") from exc

        if timestamp_ms <= 0:
            raise ValueError("Invalid trade timestamp")

        if not price.is_finite() or price <= 0:
            raise ValueError("Invalid trade price")

        if not size.is_finite() or size <= 0:
            raise ValueError("Invalid trade size")

        return cls(
            asset=asset,
            trade_id=trade_id,
            timestamp_ms=timestamp_ms,
            price_usd=price,
            size=size,
        )


# ============================================================
# COINBASE SPOT CLIENT
# ============================================================

class CoinbaseSpotClient:

    def __init__(
        self,
        timeout_seconds=15.0,
        transport=None,
    ):
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not 0 < timeout_seconds < float("inf")
        ):
            raise ValueError("Invalid timeout")

        self.client = httpx.Client(
            base_url=BASE_URL,
            timeout=timeout_seconds,
            transport=transport,
            headers={
                "Accept": "application/json",
                "User-Agent": "prediction-markets-desk/0.1",
            },
        )

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        self.close()

    # --------------------------------------------------------
    # CURRENT SPOT QUOTE
    # --------------------------------------------------------

    def get_spot_quote(self, asset):
        if not isinstance(asset, str):
            raise ValueError("Asset must be BTC or ETH")

        asset = asset.strip().upper()

        if asset not in {"BTC", "ETH"}:
            raise ValueError("Asset must be BTC or ETH")

        product_id = f"{asset}-USD"

        try:
            response = self.client.get(
                f"/products/{product_id}/ticker"
            )

            response.raise_for_status()
            data = response.json()

        except (
            httpx.RequestError,
            httpx.HTTPStatusError,
            ValueError,
        ) as exc:
            raise SpotAPIError(
                f"Failed to retrieve {product_id}"
            ) from exc

        if not isinstance(data, dict):
            raise SpotAPIError("Invalid ticker response")

        try:
            price = Decimal(str(data["price"]))

        except (
            KeyError,
            TypeError,
            InvalidOperation,
        ) as exc:
            raise SpotAPIError(
                "Invalid spot price"
            ) from exc

        if not price.is_finite() or price <= 0:
            raise SpotAPIError("Invalid spot price")

        return SpotQuote(
            asset=asset,
            product_id=product_id,
            price_usd=price,
        )

    # --------------------------------------------------------
    # HISTORICAL ONE-MINUTE CANDLES
    # --------------------------------------------------------

    def get_historical_candles(
        self,
        asset,
        start,
        end,
        granularity=60,
    ):
        if not isinstance(asset, str):
            raise ValueError("Invalid asset")

        asset = asset.strip().upper()

        if asset not in {"BTC", "ETH"}:
            raise ValueError("Unsupported asset")

        if (
            not isinstance(start, datetime)
            or not isinstance(end, datetime)
        ):
            raise ValueError(
                "Start and end must be datetimes"
            )

        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError(
                "Datetimes must be timezone-aware"
            )

        if (
            isinstance(granularity, bool)
            or granularity != 60
        ):
            raise ValueError(
                "Only 60-second candles supported"
            )

        start = start.astimezone(timezone.utc)
        end = end.astimezone(timezone.utc)

        if end <= start:
            raise ValueError("End must be after start")

        if end - start > timedelta(minutes=300):
            raise ValueError(
                "Maximum window is 300 minutes"
            )

        product_id = f"{asset}-USD"

        try:
            response = self.client.get(
                f"/products/{product_id}/candles",
                params={
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "granularity": granularity,
                },
            )

            response.raise_for_status()
            data = response.json()

        except (
            httpx.RequestError,
            httpx.HTTPStatusError,
            ValueError,
        ) as exc:
            raise SpotAPIError(
                f"Failed to retrieve {product_id} candles"
            ) from exc

        if not isinstance(data, list):
            raise SpotAPIError(
                "Invalid candle response"
            )

        try:
            candles = [
                SpotCandle.from_api(asset, item)
                for item in data
            ]

        except ValueError as exc:
            raise SpotAPIError(
                "Invalid candle data"
            ) from exc

        start_s = start.timestamp()
        end_s = end.timestamp()

        candles = [
            candle
            for candle in candles
            if (
                start_s
                <= candle.start_timestamp_s
                < end_s
            )
        ]

        return sorted(
            candles,
            key=lambda candle: candle.start_timestamp_s,
        )

    # --------------------------------------------------------
    # RECENT INDIVIDUAL TRADES
    # --------------------------------------------------------

    def get_recent_trades(
        self,
        asset,
        limit=100,
    ):
        if not isinstance(asset, str):
            raise ValueError("Invalid asset")

        asset = asset.strip().upper()

        if asset not in {"BTC", "ETH"}:
            raise ValueError("Unsupported asset")

        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 100
        ):
            raise ValueError(
                "Limit must be between 1 and 100"
            )

        product_id = f"{asset}-USD"

        try:
            response = self.client.get(
                f"/products/{product_id}/trades",
                params={"limit": limit},
            )

            response.raise_for_status()
            data = response.json()

        except (
            httpx.RequestError,
            httpx.HTTPStatusError,
            ValueError,
        ) as exc:
            raise SpotAPIError(
                f"Failed to retrieve {product_id} trades"
            ) from exc

        if not isinstance(data, list):
            raise SpotAPIError(
                "Invalid trade response"
            )

        try:
            trades = [
                SpotTrade.from_api(asset, item)
                for item in data
            ]

        except ValueError as exc:
            raise SpotAPIError(
                "Invalid trade data"
            ) from exc

        if len(trades) > limit:
            raise SpotAPIError(
                "Trade response exceeds requested limit"
            )

        trade_ids = [
            trade.trade_id
            for trade in trades
        ]

        if len(trade_ids) != len(set(trade_ids)):
            raise SpotAPIError(
                "Duplicate trade IDs"
            )

        return sorted(
            trades,
            key=lambda trade: (
                trade.timestamp_ms,
                trade.trade_id,
            ),
        )


