
from datetime import datetime, timezone

from prediction_desk.models import OrderBook


def ingest_order_book(client, storage, token_id):
    raw_book = client.get_order_book(token_id)

    book = OrderBook.from_api(raw_book)

    try:
        source_timestamp_ms = int(raw_book["timestamp"])
        book_hash = raw_book["hash"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "Missing or invalid order-book metadata"
        ) from exc

    observed_at_utc = datetime.now(
        timezone.utc
    ).isoformat()

    inserted = storage.save_order_book(
        book=book,
        source_timestamp_ms=source_timestamp_ms,
        observed_at_utc=observed_at_utc,
        book_hash=book_hash,
    )

    return {
        "token_id": book.token_id,
        "best_bid": book.best_bid,
        "best_ask": book.best_ask,
        "spread": book.spread,
        "inserted": inserted,
    }
