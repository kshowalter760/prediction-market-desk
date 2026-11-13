
from pathlib import Path

from prediction_desk.spot import CoinbaseSpotClient
from prediction_desk.spot_collector import (
    collect_spot_trades,
    format_timestamp,
)
from prediction_desk.storage import Storage


DATABASE_PATH = Path("data/prediction_markets.db")


def main():
    print("\nCoinbase live trade collection")

    with (
        CoinbaseSpotClient() as client,
        Storage(DATABASE_PATH) as storage,
    ):
        storage.initialize()

        results = collect_spot_trades(
            client=client,
            storage=storage,
            assets=("BTC", "ETH"),
            limit=100,
        )

        for result in results:
            print(f"\n{result.asset}")
            print(f"Status: {result.status}")
            print(f"Fetched: {result.fetched}")
            print(f"Inserted: {result.inserted}")
            print(
                f"Duplicates: {result.duplicate_count}"
            )
            print(
                f"Coverage: "
                f"{result.coverage_seconds:.3f} seconds"
            )
            print(
                "First trade: "
                f"{format_timestamp(result.first_trade_timestamp_ms)}"
            )
            print(
                "Last trade:  "
                f"{format_timestamp(result.last_trade_timestamp_ms)}"
            )

        print("\nDatabase totals:")
        print(
            f"BTC: {storage.count_spot_trades('BTC')}"
        )
        print(
            f"ETH: {storage.count_spot_trades('ETH')}"
        )
        print(
            f"All trades: {storage.count_spot_trades()}"
        )


        print("\nCollection audit totals:")
        print(
            "BTC runs:",
            storage.count_spot_collection_runs("BTC"),
        )
        print(
            "ETH runs:",
            storage.count_spot_collection_runs("ETH"),
        )

        for asset in ("BTC", "ETH"):
            latest = storage.get_latest_spot_collection_run(
                asset
            )

            if latest is None:
                continue

            print(f"\nLatest {asset} audit:")
            print("Status:", latest["status"])
            print("Fetched:", latest["fetched"])
            print("Inserted:", latest["inserted"])
            print(
                "Already in database:",
                latest["overlap_count"],
            )
            print(
                "Started:",
                latest["started_at_utc"],
            )
            print(
                "Completed:",
                latest["completed_at_utc"],
            )



if __name__ == "__main__":
    main()
