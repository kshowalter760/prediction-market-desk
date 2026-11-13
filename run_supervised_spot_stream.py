
from pathlib import Path

from prediction_desk.storage import Storage
from prediction_desk.stream_supervisor import (
    run_supervised_stream,
)


DATABASE_PATH = Path("data/prediction_markets.db")


def main():
    print("\nCoinbase supervised WebSocket collector")
    print("Products: BTC-USD, ETH-USD")
    print("Maximum messages: 100")
    print("Maximum connection attempts: 3")

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with Storage(DATABASE_PATH) as storage:
        storage.initialize()

        before = storage.count_spot_trades()

        result = run_supervised_stream(
            storage,
            max_messages=100,
            max_attempts=3,
            receive_timeout_seconds=10,
            backoff_seconds=1.0,
        )

        after = storage.count_spot_trades()

        print("\nSession results")
        print("Session ID:", result.session_id)
        print("Status:", result.status)
        print(
            "Termination reason:",
            result.termination_reason,
        )
        print(
            "Connection attempts:",
            result.connection_attempts,
        )
        print(
            "Messages received:",
            result.messages_received,
        )
        print(
            "Trades received:",
            result.trades_received,
        )
        print(
            "Trades inserted:",
            result.trades_inserted,
        )
        print(
            "Ignored messages:",
            result.ignored_messages,
        )
        print(
            "Potential ID gaps:",
            result.potential_id_gaps,
        )

        print("\nDatabase totals")
        print("Before:", before)
        print("After:", after)
        print(
            "BTC:",
            storage.count_spot_trades("BTC"),
        )
        print(
            "ETH:",
            storage.count_spot_trades("ETH"),
        )

        latest = storage.get_latest_spot_stream_session()

        print("\nPersisted audit")
        print("Status:", latest["status"])
        print(
            "Termination reason:",
            latest["termination_reason"],
        )
        print(
            "Recorded trades:",
            latest["trades_inserted"],
        )


if __name__ == "__main__":
    main()
