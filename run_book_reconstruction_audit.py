
import argparse
import sqlite3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database",
        default="data/prediction_markets.db",
    )
    args = parser.parse_args()

    with sqlite3.connect(args.database) as connection:
        print("\nORDER-BOOK RECONSTRUCTION READINESS")
        print("=" * 55)

        for table in (
            "order_book_snapshots",
            "market_level_updates",
        ):
            columns = connection.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()

            print(f"\n{table.upper()} COLUMNS")
            print("-" * 55)

            for column in columns:
                print(
                    f"{column[1]:25} "
                    f"{column[2]}"
                )

            count = connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            print(f"Total rows: {count}")

        print("\nSNAPSHOT COVERAGE BY TOKEN")
        print("-" * 55)

        rows = connection.execute(
            """
            SELECT
                token_id,
                COUNT(*) AS snapshots,
                MIN(source_timestamp_ms),
                MAX(source_timestamp_ms)
            FROM order_book_snapshots
            GROUP BY token_id
            ORDER BY token_id
            """
        ).fetchall()

        for token_id, count, first, last in rows:
            print(f"Token: {token_id[:18]}...")
            print(f"  Snapshots: {count}")
            print(f"  First timestamp: {first}")
            print(f"  Last timestamp:  {last}")

        print("\nLEVEL UPDATE COVERAGE BY TOKEN")
        print("-" * 55)

        rows = connection.execute(
            """
            SELECT
                token_id,
                COUNT(*) AS updates,
                MIN(source_timestamp_ms),
                MAX(source_timestamp_ms)
            FROM market_level_updates
            GROUP BY token_id
            ORDER BY token_id
            """
        ).fetchall()

        for token_id, count, first, last in rows:
            print(f"Token: {token_id[:18]}...")
            print(f"  Updates: {count}")
            print(f"  First timestamp: {first}")
            print(f"  Last timestamp:  {last}")

        print("\nSNAPSHOT TIMING RELATIVE TO UPDATES")
        print("-" * 55)

        rows = connection.execute(
            """
            SELECT
                l.token_id,
                MIN(l.source_timestamp_ms) AS first_update,
                (
                    SELECT MAX(s.source_timestamp_ms)
                    FROM order_book_snapshots AS s
                    WHERE s.token_id = l.token_id
                      AND s.source_timestamp_ms
                          <= MIN(l.source_timestamp_ms)
                ) AS preceding_snapshot
            FROM market_level_updates AS l
            GROUP BY l.token_id
            """
        ).fetchall()

        for token_id, first_update, snapshot in rows:
            print(f"Token: {token_id[:18]}...")
            print(f"  First update:       {first_update}")
            print(f"  Preceding snapshot: {snapshot}")


if __name__ == "__main__":
    main()
