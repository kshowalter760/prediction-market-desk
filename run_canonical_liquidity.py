from prediction_desk.normalized_liquidity import normalize_outcome_side
import argparse
import sqlite3
from decimal import Decimal

from prediction_desk.canonical_liquidity import (
    RawLiquidityUpdate,
    pair_liquidity_updates,
)


def load_updates(connection):
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

    return [
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


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--database",
        default="data/prediction_markets.db",
    )

    args = parser.parse_args()

    with sqlite3.connect(args.database) as connection:
        updates = load_updates(connection)

        total_raw = connection.execute(
            "SELECT COUNT(*) FROM market_level_updates"
        ).fetchone()[0]

    result = pair_liquidity_updates(updates)

    print("\nCANONICAL LIQUIDITY REPORT")
    print("=" * 45)
    print(f"Raw database rows:   {total_raw}")
    print(f"Registered updates:  {len(updates)}")
    print(f"Canonical pairs:     {len(result.events)}")
    print(f"Unmatched rows:      {len(result.unmatched_ids)}")
    print(f"Ambiguous rows:      {len(result.ambiguous_ids)}")

    accounted = (
        2 * len(result.events)
        + len(result.unmatched_ids)
        + len(result.ambiguous_ids)
    )

    assert accounted == len(updates), (
        "Pairing accounting mismatch"
    )

    print("\nSAMPLE CANONICAL EVENTS")
    print("-" * 45)

    for event in result.events[:10]:
        print(
            f"market={event.market_id} "
            f"time={event.timestamp_ms} "
            f"{event.first_outcome}/{event.first_side} "
            f"@{event.first_price} "
            f"<-> "
            f"{event.second_outcome}/{event.second_side} "
            f"@{event.second_price} "
            f"size={event.size}"
        )


    if result.events:
        market_ids = sorted({
            event.market_id
            for event in result.events
        })

        print("\nNORMALIZED UP/BUY LIQUIDITY")
        print("=" * 45)

        for market_id in market_ids:
            market_events = [
                event
                for event in result.events
                if event.market_id == market_id
            ]

            report = normalize_outcome_side(
                market_events,
                outcome="Up",
                side="BUY",
            )

            print(f"\nMarket: {market_id}")
            print(f"Canonical events:  {report.canonical_events}")
            print(f"Selected updates:  {report.normalized_updates}")
            print(f"Excluded events:   {report.excluded_events}")
            print(f"Baselines:         {report.summary['baseline']}")
            print(f"Additions:         {report.summary['addition']}")
            print(f"Reductions:        {report.summary['reduction']}")
            print(f"Removals:          {report.summary['removal']}")
            print(f"Total added:       {report.summary['total_added']}")
            print(f"Total reduced:     {report.summary['total_reduced']}")



if __name__ == "__main__":
    main()
