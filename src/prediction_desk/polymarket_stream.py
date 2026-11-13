
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


POLYMARKET_WS_URL = (
    "wss://ws-subscriptions-clob.polymarket.com/ws/market"
)


@dataclass(frozen=True)
class MarketBookEvent:
    token_id: str
    timestamp_ms: int
    bids: tuple
    asks: tuple
    book_hash: str | None




@dataclass(frozen=True)
class MarketPriceChange:
    token_id: str
    best_bid: Decimal | None
    best_ask: Decimal | None
    timestamp_ms: int | None = None
    price: Decimal | None = None
    size: Decimal | None = None
    side: str | None = None




def build_market_subscription(token_ids):
    token_ids = list(token_ids)

    if not token_ids or any(
        not isinstance(token_id, str)
        or not token_id.strip()
        for token_id in token_ids
    ):
        raise ValueError("Invalid token IDs")

    return {
        "type": "market",
        "assets_ids": token_ids,
    }


def parse_levels(levels):
    if not isinstance(levels, list):
        raise ValueError("Invalid order-book levels")

    parsed = []

    for level in levels:
        try:
            price = Decimal(str(level["price"]))
            size = Decimal(str(level["size"]))
        except (
            KeyError,
            TypeError,
            InvalidOperation,
        ) as exc:
            raise ValueError(
                "Invalid order-book level"
            ) from exc

        if (
            not price.is_finite()
            or not size.is_finite()
            or not Decimal("0") < price < Decimal("1")
            or size < 0
        ):
            raise ValueError(
                "Invalid price or size"
            )

        parsed.append((price, size))

    return tuple(parsed)


def parse_price_level_change(change):
    """Parse optional price-level information from a price_change entry."""

    fields = ("price", "size", "side")
    present = [change.get(field) is not None for field in fields]

    if not any(present):
        return None, None, None

    if not all(present):
        raise ValueError("Incomplete price-level update")

    try:
        price = Decimal(str(change["price"]))
        size = Decimal(str(change["size"]))
    except (TypeError, InvalidOperation) as exc:
        raise ValueError("Invalid price-level update") from exc

    side = change["side"]

    if (
        not price.is_finite()
        or not Decimal("0") < price < Decimal("1")
        or not size.is_finite()
        or size < 0
        or not isinstance(side, str)
        or side not in ("BUY", "SELL")
    ):
        raise ValueError("Invalid price-level update")

    return price, size, side


def parse_market_message(raw_message):
    if raw_message == "PONG":
        return []

    if isinstance(raw_message, str):
        message = json.loads(raw_message)
    else:
        message = raw_message

    if isinstance(message, list):
        events = []

        for item in message:
            events.extend(
                parse_market_message(item)
            )

        return events

    if not isinstance(message, dict):
        raise ValueError("Invalid market message")

    event_type = message.get("event_type")

    if event_type == "book":
        return [
            MarketBookEvent(
                token_id=str(message["asset_id"]),
                timestamp_ms=int(message["timestamp"]),
                bids=parse_levels(
                    message["bids"]
                ),
                asks=parse_levels(
                    message["asks"]
                ),
                book_hash=message.get("hash"),
            )
        ]


    if event_type == "price_change":
        changes = []

        raw_timestamp = message.get("timestamp")

        if raw_timestamp is None:
            timestamp_ms = None
        else:
            try:
                if isinstance(raw_timestamp, bool):
                    raise ValueError("Invalid event timestamp")

                timestamp_ms = int(raw_timestamp)

                if timestamp_ms <= 0:
                    raise ValueError("Invalid event timestamp")

            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(
                    "Invalid event timestamp"
                ) from exc

        for change in message["price_changes"]:
            try:
                best_bid = (
                    Decimal(str(change["best_bid"]))
                    if change.get("best_bid") is not None
                    else None
                )

                best_ask = (
                    Decimal(str(change["best_ask"]))
                    if change.get("best_ask") is not None
                    else None
                )

            except (TypeError, InvalidOperation) as exc:
                raise ValueError(
                    "Invalid best bid or ask"
                ) from exc

            for value in (best_bid, best_ask):
                if value is not None and (
                    not value.is_finite()
                    or not Decimal("0") <= value <= Decimal("1")
                ):
                    raise ValueError(
                        "Invalid best bid or ask"
                    )

            price, size, side = parse_price_level_change(change)

            changes.append(
                MarketPriceChange(
                    token_id=str(change["asset_id"]),
                    best_bid=best_bid,
                    best_ask=best_ask,
                    timestamp_ms=timestamp_ms,
                    price=price,
                    size=size,
                    side=side,
                )
            )

        return changes


    return []
