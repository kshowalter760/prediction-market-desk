
from pathlib import Path

from prediction_desk.discovery import (
    discover_directional_markets,
)
from prediction_desk.observation import observe_markets
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

            result = observe_markets(
                client=client,
                storage=storage,
                markets=markets,
            )

            print("\nObservation completed")
            print(
                f"Markets processed: "
                f"{result.markets_processed}"
            )
            print(
                f"Tokens attempted: "
                f"{result.tokens_attempted}"
            )
            print(
                f"Snapshots inserted: "
                f"{result.snapshots_inserted}"
            )
            print(
                f"Duplicates skipped: "
                f"{result.snapshots_duplicate}"
            )
            print(
                f"Failures: {len(result.failures)}"
            )
            print(
                f"Total stored snapshots: "
                f"{storage.count_snapshots()}"
            )

            for failure in result.failures:
                print(f"  {failure}")


if __name__ == "__main__":
    main()
