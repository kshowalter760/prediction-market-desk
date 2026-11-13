
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class OrderBookLevel:
    price: Decimal
    size: Decimal

    @classmethod
    def from_api(cls, data: dict):
        try:
            price = Decimal(str(data["price"]))
            size = Decimal(str(data["size"]))
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise ValueError(
                "Invalid order-book level"
            ) from exc

        if not price.is_finite() or not 0 < price < 1:
            raise ValueError(
                "Price must be finite and between 0 and 1"
            )

        if not size.is_finite() or size <= 0:
            raise ValueError(
                "Size must be finite and positive"
            )

        return cls(price=price, size=size)


@dataclass(frozen=True)
class OrderBook:
    token_id: str
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]

    @classmethod
    def from_api(cls, data: dict):
        try:
            token_id = str(data["asset_id"])
            raw_bids = data["bids"]
            raw_asks = data["asks"]

            if not token_id or not token_id.isdigit():
                raise ValueError("Invalid token ID")

            if not isinstance(raw_bids, list):
                raise ValueError("Bids must be a list")

            if not isinstance(raw_asks, list):
                raise ValueError("Asks must be a list")

            bids = tuple(
                OrderBookLevel.from_api(level)
                for level in raw_bids
            )

            asks = tuple(
                OrderBookLevel.from_api(level)
                for level in raw_asks
            )

        except (KeyError, TypeError) as exc:
            raise ValueError(
                "Invalid order-book response"
            ) from exc

        return cls(
            token_id=token_id,
            bids=bids,
            asks=asks,
        )

    @property
    def best_bid(self):
        if not self.bids:
            return None

        return max(level.price for level in self.bids)

    @property
    def best_ask(self):
        if not self.asks:
            return None

        return min(level.price for level in self.asks)

    @property
    def spread(self):
        if self.best_bid is None or self.best_ask is None:
            return None

        return self.best_ask - self.best_bid
