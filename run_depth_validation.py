
import sqlite3
from pathlib import Path


DATABASE = Path("data/prediction_markets.db")


def main():
    if not DATABASE.is_file():
        raise FileNotFoundError(
            f"Database not found: {DATABASE.resolve()}"
        )

    with sqlite3.connect(DATABASE) as connection:
        rows = connection.execute(
            """
            SELECT
                s.id,
                s.token_id,
                s.source_timestamp_ms,
                COUNT(l.id) AS total_levels,
                COUNT(CASE WHEN l.side = 'BUY' THEN 1 END)
                    AS bid_levels,
                COUNT(CASE WHEN l.side = 'SELL' THEN 1 END)
                    AS ask_levels
            FROM order_book_snapshots AS s
            LEFT JOIN order_book_levels AS l
                ON l.snapshot_id = s.id
            GROUP BY s.id
            ORDER BY s.id DESC
            LIMIT 10
            """
        ).fetchall()

    print("\nFULL-DEPTH SNAPSHOT VALIDATION")
    print("=" * 60)

    for snapshot_id, token_id, timestamp, total, bids, asks in rows:
        print(
            f"Snapshot {snapshot_id} | "
            f"Token {token_id[:16]}... | "
            f"Timestamp {timestamp}"
        )
        print(
            f"  Total levels: {total} | "
            f"Bids: {bids} | Asks: {asks}"
        )

    print("\nValidation complete.")


if __name__ == "__main__":
    main()
