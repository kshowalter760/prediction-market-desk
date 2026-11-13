
import argparse
import sqlite3
from collections import defaultdict
from decimal import Decimal


def load_updates(connection):
    return connection.execute(
        """
        SELECT
            id,
            token_id,
            source_timestamp_ms,
            side,
            price,
            size
        FROM market_level_updates
        WHERE source_timestamp_ms IS NOT NULL
        ORDER BY source_timestamp_ms, id
        """
    ).fetchall()


def audit_pairs(rows):
    groups = defaultdict(list)

    for row in rows:
        row_id, token_id, timestamp, side, price, size = row

        groups[timestamp].append(
            {
                "id": row_id,
                "token_id": token_id,
                "side": side,
                "price": Decimal(price),
                "size": Decimal(size),
            }
        )

    matched_ids = set()
    pairs = []
    ambiguous_groups = 0

    for timestamp, updates in groups.items():
        candidates = []

        for i, first in enumerate(updates):
            for second in updates[i + 1:]:
                if first["token_id"] == second["token_id"]:
                    continue

                if first["side"] == second["side"]:
                    continue

                if first["price"] + second["price"] != Decimal("1"):
                    continue

                if first["size"] != second["size"]:
                    continue

                candidates.append((first, second))

        counts = defaultdict(int)

        for first, second in candidates:
            counts[first["id"]] += 1
            counts[second["id"]] += 1

        if any(count > 1 for count in counts.values()):
            ambiguous_groups += 1
            continue

        for first, second in candidates:
            matched_ids.add(first["id"])
            matched_ids.add(second["id"])

            pairs.append(
                (timestamp, first, second)
            )

    print("\nCOMPLEMENTARY LIQUIDITY PAIR AUDIT")
    print("=" * 45)
    print(f"Total updates:          {len(rows)}")
    print(f"Distinct timestamps:    {len(groups)}")
    print(f"Unambiguous pairs:      {len(pairs)}")
    print(f"Matched updates:        {len(matched_ids)}")
    print(f"Unmatched updates:      {len(rows) - len(matched_ids)}")
    print(f"Ambiguous time groups:  {ambiguous_groups}")

    if rows:
        coverage = len(matched_ids) / len(rows) * 100
        print(f"Matched coverage:       {coverage:.2f}%")

    print("\nSAMPLE PAIRS")
    print("-" * 45)

    for timestamp, first, second in pairs[:10]:
        print(
            f"{timestamp} | "
            f"{first['side']} {first['price']} "
            f"<-> {second['side']} {second['price']} | "
            f"size={first['size']}"
        )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--database",
        default="data/prediction_markets.db",
    )

    args = parser.parse_args()

    with sqlite3.connect(args.database) as connection:
        rows = load_updates(connection)

    audit_pairs(rows)


if __name__ == "__main__":
    main()
