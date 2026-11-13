
import argparse
import sqlite3
from pathlib import Path

from prediction_desk.snapshot_reconstruction import (
    reconstruct_snapshot,
)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--database",
        default="data/prediction_markets.db",
    )

    parser.add_argument(
        "--snapshot-id",
        type=int,
        action="append",
        required=True,
    )

    args = parser.parse_args()

    database = Path(args.database)

    if not database.is_file():
        raise FileNotFoundError(database)

    with sqlite3.connect(database) as connection:
        for snapshot_id in args.snapshot_id:
            result = reconstruct_snapshot(
                connection,
                snapshot_id,
            )

            book = result.reconstructed

            print()
            print(f"SNAPSHOT {snapshot_id}")
            print("=" * 55)
            print(f"Token: {result.token_id}")
            print(f"Timestamp: {book.timestamp_ms}")
            print(f"Bid levels: {len(book.bids)}")
            print(f"Ask levels: {len(book.asks)}")
            print(f"Best bid: {book.best_bid}")
            print(f"Best ask: {book.best_ask}")
            print(f"Spread: {book.spread}")
            print(f"Bid depth: {book.bid_depth}")
            print(f"Ask depth: {book.ask_depth}")
            print(f"Imbalance: {book.imbalance}")
            print(
                "Metadata match:",
                "PASS" if result.matches_metadata else "FAIL",
            )


if __name__ == "__main__":
    main()
