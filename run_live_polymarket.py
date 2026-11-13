
import argparse

from prediction_desk.polymarket_live import collect_live_market
from prediction_desk.storage import Storage


def main():
    parser = argparse.ArgumentParser(
        description="Bounded Polymarket live feed test"
    )

    parser.add_argument(
        "--token-id",
        action="append",
        required=True,
        help="Outcome token ID; repeat for multiple tokens",
    )

    args = parser.parse_args()

    print("\nPolymarket live market subscriber")
    print("Tokens:", len(args.token_id))
    print("Maximum duration: 25 seconds")
    print("Maximum messages: 200")

    with Storage("data/prediction_markets.db") as storage:
        storage.initialize()

        snapshots_before = storage.count_snapshots()
        price_changes_before = storage.count_market_price_changes()

        result = collect_live_market(
            token_ids=args.token_id,
            duration_seconds=25,
            max_messages=200,
            storage=storage,
        )

        snapshots_after = storage.count_snapshots()
        price_changes_after = storage.count_market_price_changes()

    print("\nSession results")
    print("Messages:", result.messages_received)
    print("Book events:", result.book_events)
    print("Price changes:", result.price_changes)
    print("Ignored messages:", result.ignored_messages)
    print("Heartbeats sent:", result.heartbeats_sent)
    print("Termination:", result.termination_reason)

    print("\nPersistence results")
    print("Books inserted:", result.books_inserted)
    print("Price changes inserted:", result.price_changes_inserted)
    print("Duplicate books:", result.duplicate_books)

    print("\nDatabase verification")
    print(
        "Snapshots:",
        snapshots_before,
        "->",
        snapshots_after,
    )
    print(
        "Price changes:",
        price_changes_before,
        "->",
        price_changes_after,
    )


if __name__ == "__main__":
    main()

