
from pathlib import Path

from prediction_desk.discovery import (
    discover_directional_markets,
)
from prediction_desk.polymarket import PolymarketClient
from prediction_desk.storage import Storage


DATABASE_PATH = Path("data/prediction_markets.db")


def main():
    with PolymarketClient() as client:
        markets = discover_directional_markets(
            client,
            future_intervals=2,
        )

    with Storage(DATABASE_PATH) as storage:
        storage.initialize()

        for market in markets:
            storage.save_market(market)

        print(f"Discovered markets: {len(markets)}")
        print(f"Stored markets: {storage.count_markets()}")
        print(f"Stored outcomes: {storage.count_outcomes()}")
        print(
            f"Historical snapshots: "
            f"{storage.count_snapshots()}"
        )


if __name__ == "__main__":
    main()
