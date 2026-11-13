
import sqlite3
from collections import defaultdict
from decimal import Decimal

from prediction_desk.canonical_liquidity import (
    RawLiquidityUpdate,
    pair_liquidity_updates,
)


DATABASE = "data/prediction_markets.db"


def main():
    with sqlite3.connect(DATABASE) as connection:
        rows = connection.execute(
            """
            SELECT
                l.id,
                o.market_id,
                l.token_id,
                o.outcome_name,
                l.source_timestamp_ms,
                l.side,
                l.price,
                l.size
            FROM market_level_updates AS l
            JOIN outcomes AS o
                ON l.token_id = o.token_id
            WHERE l.source_timestamp_ms IS NOT NULL
            ORDER BY
                o.market_id,
                l.source_timestamp_ms,
                l.id
            """
        ).fetchall()

    updates = [
        RawLiquidityUpdate(
            row_id=row[0],
            market_id=str(row[1]),
            token_id=row[2],
            outcome_name=row[3],
            timestamp_ms=row[4],
            side=row[5],
            price=Decimal(row[6]),
            size=Decimal(row[7]),
        )
        for row in rows
    ]

    result = pair_liquidity_updates(updates)

    counts = defaultdict(int)
    pair_types = defaultdict(int)

    for event in result.events:
        counts[
            (event.first_outcome, event.first_side)
        ] += 1

        counts[
            (event.second_outcome, event.second_side)
        ] += 1

        pair_type = tuple(
            sorted([
                (
                    event.first_outcome,
                    event.first_side,
                ),
                (
                    event.second_outcome,
                    event.second_side,
                ),
            ])
        )

        pair_types[pair_type] += 1

    print("\nOUTCOME-SIDE COVERAGE AUDIT")
    print("=" * 50)

    for outcome in ("Up", "Down"):
        for side in ("BUY", "SELL"):
            print(
                f"{outcome:4} / {side:4}: "
                f"{counts[(outcome, side)]}"
            )

    print("\nCOMPLEMENTARY PAIR TYPES")
    print("-" * 50)

    for pair_type, count in sorted(pair_types.items()):
        print(f"{pair_type}: {count}")

    print("\nPAIRING INTEGRITY")
    print("-" * 50)
    print(f"Canonical pairs: {len(result.events)}")
    print(f"Unmatched:       {len(result.unmatched_ids)}")
    print(f"Ambiguous:       {len(result.ambiguous_ids)}")


if __name__ == "__main__":
    main()
