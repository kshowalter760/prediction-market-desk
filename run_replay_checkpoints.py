
import argparse
import sqlite3
from pathlib import Path

from prediction_desk.replay_checkpoints import (
    reconstruct_checkpoints,
)


DATABASE = Path("data/prediction_markets.db")


def main():
    parser = argparse.ArgumentParser(
        description="Reconstruct historical order-book checkpoints"
    )

    parser.add_argument(
        "--session-id",
        type=int,
        default=None,
        help="Polymarket stream session ID",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Checkpoint interval in seconds",
    )

    args = parser.parse_args()

    if args.interval <= 0:
        parser.error("--interval must be positive")

    if not DATABASE.is_file():
        raise FileNotFoundError(
            f"Database not found: {DATABASE}"
        )

    uri = f"file:{DATABASE.resolve().as_posix()}?mode=ro"

    with sqlite3.connect(uri, uri=True) as connection:
        session_id = args.session_id

        if session_id is None:
            row = connection.execute(
                """
                SELECT id
                FROM polymarket_stream_sessions
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "No Polymarket stream sessions found"
                )

            session_id = row[0]

        snapshots = connection.execute(
            """
            SELECT id, token_id
            FROM order_book_snapshots
            WHERE stream_session_id = ?
            ORDER BY id
            """,
            (session_id,),
        ).fetchall()

        print()
        print("HISTORICAL REPLAY CHECKPOINTS")
        print("=" * 70)
        print("Session:", session_id)
        print("Interval:", args.interval, "seconds")
        print("Initial snapshots:", len(snapshots))

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
            print("Checkpoints:", len(checkpoints))

            for checkpoint in checkpoints:
                book = checkpoint.book

                print(
                    f"SEQ={checkpoint.message_sequence} "
                    f"TIME={checkpoint.timestamp_ms} "
                    f"BID={book.best_bid} "
                    f"ASK={book.best_ask} "
                    f"SPREAD={book.spread} "
                    f"IMBALANCE={book.imbalance}"
                )


if __name__ == "__main__":
    main()
