
from pathlib import Path

from prediction_desk.polling import run_spot_polling
from prediction_desk.spot import CoinbaseSpotClient
from prediction_desk.storage import Storage


DATABASE_PATH = Path("data/prediction_markets.db")


def print_cycle(cycle_number, results):
    print(f"\nCycle {cycle_number}")

    for result in results:
        print(
            f"  {result.asset}: "
            f"{result.status} | "
            f"fetched={result.fetched} | "
            f"inserted={result.inserted} | "
            f"duplicates={result.duplicate_count} | "
            f"span={result.coverage_seconds:.2f}s"
        )


def main():
    print("\nStarting Coinbase live polling")
    print("Assets: BTC, ETH")
    print("Interval: 5 seconds")
    print("Maximum cycles: 3")
    print("Press Ctrl+C to stop early.")

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with (
        CoinbaseSpotClient() as client,
        Storage(DATABASE_PATH) as storage,
    ):
        storage.initialize()

        summary = run_spot_polling(
            client=client,
            storage=storage,
            assets=("BTC", "ETH"),
            limit=100,
            interval_seconds=5.0,
            max_cycles=3,
            on_cycle=print_cycle,
        )

        print("\nPolling summary")
        print("Cycles:", summary.cycles_completed)
        print("Fetched:", summary.total_fetched)
        print("Inserted:", summary.total_inserted)
        print("Duplicates:", summary.total_duplicates)
        print("API errors:", summary.api_errors)
        print("Stopped early:", summary.stopped_early)

        print("\nDatabase totals")
        print("BTC:", storage.count_spot_trades("BTC"))
        print("ETH:", storage.count_spot_trades("ETH"))
        print(
            "Audited collection runs:",
            storage.count_spot_collection_runs(),
        )


if __name__ == "__main__":
    main()
