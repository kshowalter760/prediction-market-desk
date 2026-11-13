
import argparse
import sqlite3
from collections import Counter
from pathlib import Path

from prediction_desk.cross_market_alignment import (
    align_checkpoints,
)
from prediction_desk.replay_checkpoints import (
    reconstruct_checkpoints,
)


DATABASE = Path("data/prediction_markets.db")


def main():
    parser = argparse.ArgumentParser(
        description="Align Polymarket checkpoints with Coinbase spot trades"
    )

    parser.add_argument(
        "--session-id",
        type=int,
        required=True,
        help="Polymarket stream session ID",
    )

    parser.add_argument(
        "--asset",
        choices=("BTC", "ETH"),
        default="BTC",
        help="Coinbase spot asset",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Checkpoint interval in seconds",
    )

    parser.add_argument(
        "--max-spot-age-ms",
        type=int,
        default=5000,
        help="Maximum acceptable spot trade age in milliseconds",
    )

    args = parser.parse_args()

    if args.session_id <= 0:
        parser.error("--session-id must be positive")

    if args.interval <= 0:
        parser.error("--interval must be positive")

    if args.max_spot_age_ms < 0:
        parser.error("--max-spot-age-ms cannot be negative")

    if not DATABASE.is_file():
        raise FileNotFoundError(
            f"Database not found: {DATABASE}"
        )

    uri = f"file:{DATABASE.resolve().as_posix()}?mode=ro"

    with sqlite3.connect(uri, uri=True) as connection:
        snapshots = connection.execute(
            """
            SELECT id, token_id
            FROM order_book_snapshots
            WHERE stream_session_id = ?
            ORDER BY id
            """,
            (args.session_id,),
        ).fetchall()

        print()
        print("CROSS-MARKET TIMESTAMP ALIGNMENT")
        print("=" * 75)
        print("Polymarket session:", args.session_id)
        print("Coinbase asset:", args.asset)
        print("Checkpoint interval:", args.interval, "seconds")
        print("Maximum spot age:", args.max_spot_age_ms, "ms")
        print("Initial snapshots:", len(snapshots))

        if not snapshots:
            print("No snapshots found for this session.")
            return

        all_results = []

        for snapshot_id, token_id in snapshots:
            checkpoints = reconstruct_checkpoints(
                connection,
                snapshot_id,
                interval_ms=args.interval * 1000,
            )

            results = align_checkpoints(
                connection,
                checkpoints,
                asset=args.asset,
                max_spot_age_ms=args.max_spot_age_ms,
            )

            all_results.extend(results)

            print()
            print("-" * 75)
            print("Token:", token_id[:20] + "...")
            print("Snapshot:", snapshot_id)
            print("Checkpoints:", len(checkpoints))

            for result in results:
                print(
                    f"SEQ={result.message_sequence} "
                    f"TIME={result.checkpoint_timestamp_ms} "
                    f"POLY_MID={result.polymarket_mid_price} "
                    f"SPOT={result.spot_price_usd} "
                    f"AGE_MS={result.spot_age_ms} "
                    f"STATUS={result.alignment_status}"
                )

        counts = Counter(
            result.alignment_status
            for result in all_results
        )

        print()
        print("=" * 75)
        print("ALIGNMENT SUMMARY")
        print("Total observations:", len(all_results))
        print("Aligned:", counts["aligned"])
        print("Stale:", counts["stale_spot"])
        print("Missing:", counts["missing_spot"])

        if all_results:
            aligned_count = counts["aligned"]
            alignment_rate = (
                100 * aligned_count / len(all_results)
            )

            print(
                f"Alignment rate: {alignment_rate:.2f}%"
            )

        print()
        print(
            "Note: Event-time alignment only; "
            "not proof of live information availability."
        )


if __name__ == "__main__":
    main()
