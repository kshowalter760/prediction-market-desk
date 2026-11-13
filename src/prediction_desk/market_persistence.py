
from dataclasses import dataclass
from datetime import datetime, timezone

from prediction_desk.models import OrderBook, OrderBookLevel
from prediction_desk.polymarket_stream import (
    MarketBookEvent,
    MarketPriceChange,
)


@dataclass(frozen=True)
class PersistedMarketEvent:
    event_type: str
    inserted: bool


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def convert_book_event(event: MarketBookEvent) -> OrderBook:
    if not isinstance(event, MarketBookEvent):
        raise TypeError("Expected MarketBookEvent")

    return OrderBook(
        token_id=event.token_id,
        bids=tuple(
            OrderBookLevel(price=price, size=size)
            for price, size in event.bids
        ),
        asks=tuple(
            OrderBookLevel(price=price, size=size)
            for price, size in event.asks
        ),
    )


def persist_market_event(
    storage,
    event,
    *,
    stream_session_id=None,
    message_sequence=None,
):
    if isinstance(event, MarketBookEvent):
        book = convert_book_event(event)

        # Validate against existing order-book contracts.
        if not book.token_id.isdigit():
            raise ValueError("Invalid token ID")

        for level in (*book.bids, *book.asks):
            OrderBookLevel.from_api(
                {
                    "price": str(level.price),
                    "size": str(level.size),
                }
            )

        if not event.book_hash:
            raise ValueError("Missing book hash")

        # Full order-book snapshots go to this table.
        inserted = storage.save_order_book(
            book=book,
            source_timestamp_ms=event.timestamp_ms,
            observed_at_utc=utc_now(),
            book_hash=event.book_hash,
            stream_session_id=stream_session_id,
            message_sequence=message_sequence,
        )

        return PersistedMarketEvent(
            event_type="book",
            inserted=inserted,
        )

    if isinstance(event, MarketPriceChange):
        if not event.token_id.isdigit():
            raise ValueError("Invalid token ID")

        has_level = any(
            value is not None
            for value in (
                event.price,
                event.size,
                event.side,
            )
        )

        if has_level and (
            event.price is None
            or event.size is None
            or event.side is None
        ):
            raise ValueError("Incomplete price-level update")

        inserted = storage.save_atomic_market_price_change(
            token_id=event.token_id,
            best_bid=event.best_bid,
            best_ask=event.best_ask,
            observed_at_utc=utc_now(),
            source_timestamp_ms=event.timestamp_ms,
            price=event.price,
            size=event.size,
            side=event.side,
            stream_session_id=stream_session_id,
            message_sequence=message_sequence,
        )

        return PersistedMarketEvent(
            event_type="price_change",
            inserted=inserted,
        )

    raise TypeError(
        f"Unsupported market event type: {type(event).__name__}"
    )

