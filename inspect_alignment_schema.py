
import sqlite3
from pathlib import Path

DATABASE_PATH = Path("data/prediction_markets.db")

TABLES = (
    "spot_trades",
    "order_book_snapshots",
    "market_price_changes",
    "markets",
    "outcomes",
)


def main():
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        for table in TABLES:
            print(f"\n{'=' * 65}")
            print(f"TABLE: {table}")
            print("=" * 65)

            columns = connection.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()

            if not columns:
                print("Table not found")
                continue

            for column in columns:
                print(
                    f"{column[1]:30} "
                    f"{column[2]}"
                )

            count = connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            print(f"\nRows: {count}")

            rows = connection.execute(
                f"SELECT * FROM {table} LIMIT 2"
            ).fetchall()

            print("\nSample records:")

            for row in rows:
                for column, value in zip(columns, row):
                    print(f"  {column[1]}: {value}")
                print()

    finally:
        connection.close()


if __name__ == "__main__":
    main()
