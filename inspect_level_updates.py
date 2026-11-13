
import sqlite3
from collections import Counter
from pathlib import Path

DATABASE = Path("data/prediction_markets.db")


def main():
    with sqlite3.connect(DATABASE) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT
                token_id,
                source_timestamp_ms,
                price,
                size,
                side
            FROM market_level_updates
            ORDER BY id DESC
            LIMIT 1000
            """
        ).fetchall()

    print("\nMARKET LEVEL UPDATE REPORT")
    print("=" * 60)

    print(f"Recent level updates: {len(rows)}")

    if not rows:
        print("No level updates recorded yet.")
        return

    print(f"Unique tokens: {len(set(r['token_id'] for r in rows))}")
    print(f"Unique prices: {len(set(r['price'] for r in rows))}")
    print(f"BUY updates: {sum(r['side'] == 'BUY' for r in rows)}")
    print(f"SELL updates: {sum(r['side'] == 'SELL' for r in rows)}")
    print(f"Zero-size updates: {sum(float(r['size']) == 0 for r in rows)}")

    print("\nMOST FREQUENT PRICE LEVELS")
    print("=" * 60)

    for price, count in Counter(
        r["price"] for r in rows
    ).most_common(10):
        print(f"{price}: {count}")

    print("\nLATEST 10 UPDATES")
    print("=" * 60)

    for row in rows[:10]:
        print(
            f"{row['side']} "
            f"price={row['price']} "
            f"size={row['size']} "
            f"timestamp={row['source_timestamp_ms']}"
        )


if __name__ == "__main__":
    main()
