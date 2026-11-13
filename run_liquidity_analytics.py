
import argparse
import sqlite3
from pathlib import Path

from prediction_desk.checkpoint_analytics import (
    observation_from_checkpoint,
    summarize_checkpoints,
)
from prediction_desk.replay_checkpoints import (
    reconstruct_checkpoints,
)


DATABASE = Path("data/prediction_markets.db")


def main():
    parser = argparse.ArgumentParser(
        description="Historical order-book liquidity analytics"
    )

    parser.add_argument(
        "--session-id",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Checkpoint interval in seconds",
    )

    args = parser.parse_args()

    if args.session_id <= 0:
        parser.error("--session-id must be positive")

    if args.interval <= 0:
        parser.error("--interval must be positive")

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
        print("HISTORICAL LIQUIDITY ANALYTICS")
        print("=" * 70)
        print("Session:", args.session_id)
        print("Interval:", args.interval, "seconds")
        print("Snapshots:", len(snapshots))

        if not snapshots:
            print("No snapshots found for this session.")
            return

        for snapshot_id, token_id in snapshots:
            checkpoints = reconstruct_checkpoints(
                connection,
                snapshot_id,
                interval_ms=args.interval * 1000,
            )

            print()
            print("-" * 70)
            print("Token:", token_id[:20] + "...")
            print("Initial snapshot:", snapshot_id)

            if not checkpoints:
                print("No checkpoints available.")
                continue

            observations = [
                observation_from_checkpoint(checkpoint)
                for checkpoint in checkpoints
            ]

            summary = summarize_checkpoints(observations)

            print("Observations:", summary.observation_count)
            print("Average spread:", summary.average_spread)
            print("Minimum spread:", summary.minimum_spread)
            print("Maximum spread:", summary.maximum_spread)
            print("Average total depth:", summary.average_total_depth)
            print("Average imbalance:", summary.average_imbalance)
            print("First mid-price:", summary.first_mid_price)
            print("Last mid-price:", summary.last_mid_price)
            print("Mid-price change:", summary.mid_price_change)


if __name__ == "__main__":
    main()
