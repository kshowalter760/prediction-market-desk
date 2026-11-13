
import time
from pathlib import Path

from prediction_desk.discovery import (
    discover_directional_markets,
)
from prediction_desk.observation import observe_markets
from prediction_desk.polymarket import PolymarketClient
from prediction_desk.storage import Storage


DATABASE_PATH = Path("data/prediction_markets.db")

COLLECTION_CYCLES = 3
INTERVAL_SECONDS = 20


def main():
    with PolymarketClient() as client:
        markets = discover_directional_markets(
            client,
            future_intervals=0,
        )

        print(f"Markets selected: {len(markets)}")

        if not markets:
            print("No eligible markets found")
            return

        with Storage(DATABASE_PATH) as storage:
            storage.initialize()

            for cycle in range(COLLECTION_CYCLES):
                print(
                    f"\nCollection cycle "
                    f"{cycle + 1}/{COLLECTION_CYCLES}"
                )

                result = observe_markets(
                    client=client,
                    storage=storage,
                    markets=markets,
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

                for failure in result.failures:
                    print(f"  {failure}")

                if cycle < COLLECTION_CYCLES - 1:
                    time.sleep(INTERVAL_SECONDS)

            print("\nCollection finished")
            print(
                f"Total database snapshots: "
                f"{storage.count_snapshots()}"
            )

            print("\nOutcome history summary:")

            for market in markets:
                for outcome_name, token_id in market.outcome_tokens:
                    history = storage.get_outcome_history(
                        token_id,
                        limit=100,
                    )

                    print(
                        f"{market.asset} {outcome_name}: "
                        f"{len(history)} observations"
                    )

                    for row in history[:3]:
                        print(
                            f"  {row['source_timestamp_ms']} "
                            f"bid={row['best_bid']} "
                            f"ask={row['best_ask']}"
                        )


if __name__ == "__main__":
    main()
