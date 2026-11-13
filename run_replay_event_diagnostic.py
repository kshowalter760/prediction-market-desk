
import sqlite3
from pathlib import Path


DATABASE = Path("data/prediction_markets.db")

SESSION_ID = 3
START_SEQUENCE = 500
END_SEQUENCE = 507


def main():
    if not DATABASE.is_file():
        raise FileNotFoundError(DATABASE)

    connection = sqlite3.connect(
        f"file:{DATABASE.resolve().as_posix()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row

    try:
        print("LEVEL UPDATES AROUND FAILURE")
        print("=" * 80)

        rows = connection.execute(
            """
            SELECT
                id,
                token_id,
                message_sequence,
                source_timestamp_ms,
                side,
                price,
                size
            FROM market_level_updates
            WHERE stream_session_id = ?
              AND message_sequence BETWEEN ? AND ?
            ORDER BY message_sequence, id
            """,
            (
                SESSION_ID,
                START_SEQUENCE,
                END_SEQUENCE,
            ),
        ).fetchall()

        for row in rows:
            print(
                f"ID={row['id']} "
                f"SEQ={row['message_sequence']} "
                f"TOKEN={row['token_id'][:16]}... "
                f"SIDE={row['side']} "
                f"PRICE={row['price']} "
                f"SIZE={row['size']} "
                f"TIME={row['source_timestamp_ms']}"
            )

        print()
        print("SNAPSHOTS AROUND FAILURE")
        print("=" * 80)

        snapshots = connection.execute(
            """
            SELECT
                id,
                token_id,
                message_sequence,
                source_timestamp_ms,
                best_bid,
                best_ask
            FROM order_book_snapshots
            WHERE stream_session_id = ?
              AND message_sequence BETWEEN ? AND ?
            ORDER BY message_sequence, id
            """,
            (
                SESSION_ID,
                START_SEQUENCE,
                END_SEQUENCE,
            ),
        ).fetchall()

        for row in snapshots:
            print(dict(row))

    finally:
        connection.close()


if __name__ == "__main__":
    main()
