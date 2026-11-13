
import json
from dataclasses import dataclass

from prediction_desk.spot import SpotTrade


COINBASE_WS_URL = (
    "wss://ws-feed.exchange.coinbase.com"
)

PRODUCTS = {
    "BTC-USD": "BTC",
    "ETH-USD": "ETH",
}


@dataclass(frozen=True)
class StreamResult:
    messages_received: int
    trades_received: int
    trades_inserted: int
    ignored_messages: int


def build_subscription():
    return {
        "type": "subscribe",
        "product_ids": list(PRODUCTS),
        "channels": ["matches"],
    }


def parse_trade_message(message):
    if not isinstance(message, dict):
        raise ValueError("Invalid stream message")

    if message.get("type") != "match":
        return None

    product_id = message.get("product_id")

    if product_id not in PRODUCTS:
        return None

    return SpotTrade.from_api(
        PRODUCTS[product_id],
        message,
    )


def process_trade_messages(
    messages,
    storage,
    max_messages=20,
    on_trade=None,
):
    if (
        not isinstance(max_messages, int)
        or isinstance(max_messages, bool)
        or max_messages <= 0
    ):
        raise ValueError("Invalid message limit")

    received = 0
    trades_received = 0
    trades_inserted = 0
    ignored = 0

    for raw_message in messages:
        if received >= max_messages:
            break

        received += 1

        if on_trade is not None and not callable(on_trade):
            raise TypeError("on_trade must be callable")

        if isinstance(raw_message, str):
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Invalid stream JSON"
                ) from exc
        else:
            message = raw_message

        trade = parse_trade_message(message)

        if trade is None:
            ignored += 1
            continue

        trades_received += 1

        trades_inserted += storage.save_spot_trades(
            [trade]
        )

        if on_trade is not None:
            on_trade(trade)

    return StreamResult(
        messages_received=received,
        trades_received=trades_received,
        trades_inserted=trades_inserted,
        ignored_messages=ignored,
    )


def collect_live_stream(
    storage,
    max_messages=100,
    receive_timeout_seconds=10,
    on_trade=None,
):
    from websockets.sync.client import connect

    if (
        not isinstance(max_messages, int)
        or isinstance(max_messages, bool)
        or max_messages <= 0
    ):
        raise ValueError("Invalid message limit")

    if (
        isinstance(receive_timeout_seconds, bool)
        or not isinstance(
            receive_timeout_seconds, (int, float)
        )
        or not 0 < receive_timeout_seconds < float("inf")
    ):
        raise ValueError("Invalid receive timeout")

    with connect(
        COINBASE_WS_URL,
        open_timeout=15,
        close_timeout=5,
    ) as websocket:
        websocket.send(
            json.dumps(build_subscription())
        )

        def incoming_messages():
            for _ in range(max_messages):
                try:
                    yield websocket.recv(
                        timeout=receive_timeout_seconds
                    )
                except TimeoutError:
                    return

        return process_trade_messages(
            incoming_messages(),
            storage,
            max_messages=max_messages,
            on_trade=on_trade,
        )
