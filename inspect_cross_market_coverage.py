
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DATABASE = Path("data/prediction_markets.db")


def format_timestamp(timestamp_ms):
    if timestamp_ms is None:
        return "NULL"

    return datetime.fromtimestamp(
        timestamp_ms / 1000,
        tz=timezone.utc,
    ).isoformat()


def main():
    if not DATABASE.is_file():
        raise FileNotFoundError(DATABASE)

    connection = sqlite3.connect(
        DATABASE.resolve().as_uri() + "?mode=ro",
        uri=True,
    )

    try:
        print("\nCOINBASE TRADE COVERAGE")
        print("=" * 60)

        rows = connection.execute(
            """
            SELECT
                asset,
                COUNT(*),
                MIN(trade_timestamp_ms),
                MAX(trade_timestamp_ms),
                MIN(observed_at_utc),
                MAX(observed_at_utc)
            FROM spot_trades
            GROUP BY asset
            """
        ).fetchall()

        for asset, count, first, last, observed_first, observed_last in rows:
            print(f"\nAsset: {asset}")
            print(f"Trades: {count}")
            print(f"First source: {format_timestamp(first)}")
            print(f"Last source:  {format_timestamp(last)}")
            print(f"First observed: {observed_first}")
            print(f"Last observed:  {observed_last}")

        print("\nPOLYMARKET EVENT COVERAGE")
        print("=" * 60)

        for table in (
            "order_book_snapshots",
            "market_price_changes",
        ):
            count, timed, first, last = connection.execute(
                f"""
                SELECT
                    COUNT(*),
                    COUNT(source_timestamp_ms),
                    MIN(source_timestamp_ms),
                    MAX(source_timestamp_ms)
                FROM {table}
                """
            ).fetchone()

            print(f"\nTable: {table}")
            print(f"Rows: {count}")
            print(f"With source timestamp: {timed}")
            print(f"First source: {format_timestamp(first)}")
            print(f"Last source:  {format_timestamp(last)}")

        print("\nMARKET REGISTRY COVERAGE")
        print("=" * 60)

        for table in (
            "order_book_snapshots",
            "market_price_changes",
        ):
            total, registered = connection.execute(
                f"""
                SELECT
                    COUNT(*),
                    COUNT(o.token_id)
                FROM {table} AS e
                LEFT JOIN outcomes AS o
                    ON o.token_id = e.token_id
                """
            ).fetchone()

            print(
                f"{table}: "
                f"{registered}/{total} registered"
            )

        print("\nLATEST COORDINATED SESSION")
        print("=" * 60)

        start = "2026-10-28T17:57:16"
        end = "2026-10-28T17:57:49"

        for table, timestamp_column in (
            ("spot_trades", "trade_timestamp_ms"),
            ("order_book_snapshots", "source_timestamp_ms"),
            ("market_price_changes", "source_timestamp_ms"),
        ):
            count, first, last = connection.execute(
                f"""
                SELECT
                    COUNT(*),
                    MIN({timestamp_column}),
                    MAX({timestamp_column})
                FROM {table}
                WHERE observed_at_utc >= ?
                  AND observed_at_utc < ?
                """,
                (start, end),
            ).fetchone()

            print(f"\n{table}")
            print(f"Rows: {count}")
            print(f"First source: {format_timestamp(first)}")
            print(f"Last source:  {format_timestamp(last)}")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
