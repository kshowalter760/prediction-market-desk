
import json
from pathlib import Path

from prediction_desk.polymarket import PolymarketClient
from prediction_desk.scanner import ingest_order_book
from prediction_desk.storage import Storage


DATABASE_PATH = Path("data/prediction_markets.db")


def main():
    with PolymarketClient() as client:
        markets = client.get_markets(limit=20)

        selected_market = None
        selected_token_id = None

        for market in markets:
            if not market.get("enableOrderBook"):
                continue

            raw_token_ids = market.get("clobTokenIds")

            if not raw_token_ids:
                continue

            token_ids = json.loads(raw_token_ids)

            if not token_ids:
                continue

            selected_market = market
            selected_token_id = token_ids[0]
            break

        if selected_token_id is None:
            print("No eligible market found.")
            return

        print(f"Market: {selected_market['question']}")

        with Storage(DATABASE_PATH) as storage:
            storage.initialize()

            result = ingest_order_book(
                client=client,
                storage=storage,
                token_id=selected_token_id,
            )

            print(f"Token: {result['token_id']}")
            print(f"Best bid: {result['best_bid']}")
            print(f"Best ask: {result['best_ask']}")
            print(f"Spread: {result['spread']}")
            print(f"Inserted: {result['inserted']}")
            print(
                f"Total snapshots: "
                f"{storage.count_snapshots()}"
            )


if __name__ == "__main__":
    main()
