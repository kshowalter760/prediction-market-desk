
import argparse
import sqlite3
from decimal import Decimal

from prediction_desk.liquidity_analytics import (
    LevelUpdate,
    analyze_liquidity,
    summarize_liquidity,
)


def load_updates(connection, token_id=None):
    sql = """
        SELECT
            token_id,
            source_timestamp_ms,
            side,
            price,
            size
        FROM market_level_updates
        WHERE source_timestamp_ms IS NOT NULL
    """

    params = []

    if token_id is not None:
        sql += " AND token_id = ?"
        params.append(token_id)

    sql += """
        ORDER BY
            source_timestamp_ms ASC,
            id ASC
    """

    rows = connection.execute(sql, params).fetchall()

    return [
        LevelUpdate(
            token_id=row[0],
            timestamp_ms=row[1],
            side=row[2],
            price=Decimal(row[3]),
            size=Decimal(row[4]),
        )
        for row in rows
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Polymarket liquidity movement report"
    )

    parser.add_argument(
        "--database",
        default="data/prediction_markets.db",
    )

    parser.add_argument(
        "--token-id",
        default=None,
    )

    args = parser.parse_args()

    with sqlite3.connect(args.database) as connection:
        updates = load_updates(
            connection,
            token_id=args.token_id,
        )

    if not updates:
        print("No liquidity updates found.")
        return

    movements = analyze_liquidity(updates)
    summary = summarize_liquidity(movements)

    print("\nPOLYMARKET LIQUIDITY MOVEMENT REPORT")
    print("=" * 45)

    print(f"Raw updates:        {len(updates)}")
    print(f"Analyzed movements: {len(movements)}")
    print(f"Initial baselines:  {summary['baseline']}")
    print(f"Additions:          {summary['addition']}")
    print(f"Reductions:         {summary['reduction']}")
    print(f"Removals:           {summary['removal']}")
    print(f"Unchanged:          {summary['unchanged']}")

    print()
    print(f"Total size added:   {summary['total_added']}")
    print(f"Total size reduced: {summary['total_reduced']}")

    print("\nRECENT MOVEMENTS")
    print("-" * 45)

    for movement in movements[-10:]:
        print(
            f"{movement.token_id[:12]}... "
            f"{movement.side:4} "
            f"price={movement.price} "
            f"size={movement.current_size} "
            f"delta={movement.size_change} "
            f"type={movement.classification}"
        )


if __name__ == "__main__":
    main()
