
import json
import math
import time
from dataclasses import dataclass

from websockets.sync.client import connect

from prediction_desk.market_persistence import persist_market_event
from prediction_desk.polymarket_stream import (
    POLYMARKET_WS_URL,
    MarketBookEvent,
    MarketPriceChange,
    build_market_subscription,
    parse_market_message,
)
from prediction_desk.stream_sessions import (
    start_stream_session,
    finish_stream_session,
)


@dataclass(frozen=True)
class LiveMarketResult:
    messages_received: int
    book_events: int
    price_changes: int
    ignored_messages: int
    heartbeats_sent: int
    termination_reason: str
    books_inserted: int
    price_changes_inserted: int
    duplicate_books: int


def collect_live_market(
    token_ids,
    duration_seconds=25,
    max_messages=200,
    storage=None,
    connect_fn=connect,
    clock_fn=time.monotonic,
    start_session_fn=start_stream_session,
    finish_session_fn=finish_stream_session,
):
    if (
        not isinstance(duration_seconds, (int, float))
        or isinstance(duration_seconds, bool)
        or not math.isfinite(duration_seconds)
        or duration_seconds <= 0
    ):
        raise ValueError("Invalid duration")

    if type(max_messages) is not int or max_messages <= 0:
        raise ValueError("Invalid message limit")

    subscription = build_market_subscription(token_ids)

    messages = 0
    books = 0
    changes = 0
    ignored = 0
    heartbeats = 0
    books_inserted = 0
    changes_inserted = 0
    duplicate_books = 0

    with connect_fn(
        POLYMARKET_WS_URL,
        open_timeout=15,
        close_timeout=5,
    ) as websocket:

        session_id = (
            start_session_fn(storage.connection)
            if storage is not None
            else None
        )

        session_status = "completed"
        disconnect_reason = None
        termination_reason = "duration_limit"

        try:
            websocket.send(json.dumps(subscription))

            started = clock_fn()
            deadline = started + duration_seconds
            next_ping = started + 10

            while messages < max_messages:
                now = clock_fn()

                if now >= deadline:
                    break

                if now >= next_ping:
                    websocket.send("PING")
                    heartbeats += 1
                    next_ping = now + 10

                timeout = min(
                    1.0,
                    deadline - now,
                    max(0.01, next_ping - now),
                )

                try:
                    raw = websocket.recv(timeout=timeout)
                except TimeoutError:
                    continue

                messages += 1
                events = parse_market_message(raw)

                if not events:
                    ignored += 1

                for event in events:

                    if isinstance(event, MarketBookEvent):
                        books += 1

                        if storage is not None:
                            result = persist_market_event(
                                storage,
                                event,
                                stream_session_id=session_id,
                                message_sequence=messages,
                            )

                            if result.inserted:
                                books_inserted += 1
                            else:
                                duplicate_books += 1

                        print(
                            f"BOOK token={event.token_id[:16]}... "
                            f"bids={len(event.bids)} "
                            f"asks={len(event.asks)}"
                        )

                    elif isinstance(event, MarketPriceChange):
                        changes += 1

                        if storage is not None:
                            result = persist_market_event(
                                storage,
                                event,
                                stream_session_id=session_id,
                                message_sequence=messages,
                            )

                            if result.inserted:
                                changes_inserted += 1

                        if changes % 25 == 0:
                            print(
                                f"PRICE updates received: {changes}"
                            )

            if messages >= max_messages:
                termination_reason = "message_limit"

        except Exception as exc:
            session_status = "failed"
            disconnect_reason = (
                f"{type(exc).__name__}: {exc}"
            )
            raise

        finally:
            if session_id is not None:
                finish_session_fn(
                    storage.connection,
                    session_id,
                    status=session_status,
                    disconnect_reason=disconnect_reason,
                )

    return LiveMarketResult(
        messages_received=messages,
        book_events=books,
        price_changes=changes,
        ignored_messages=ignored,
        heartbeats_sent=heartbeats,
        termination_reason=termination_reason,
        books_inserted=books_inserted,
        price_changes_inserted=changes_inserted,
        duplicate_books=duplicate_books,
    )
