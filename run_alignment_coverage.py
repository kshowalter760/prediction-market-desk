
import argparse
from bisect import bisect_right
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


def utc_time(timestamp_ms):
    if timestamp_ms is None:
        return "N/A"

    return datetime.fromtimestamp(
        timestamp_ms / 1000,
        tz=timezone.utc,
    ).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database",
        default="data/prediction_markets.db",
    )
    parser.add_argument(
        "--max-age-ms",
        type=int,
        default=5000,
    )

    args = parser.parse_args()

    if args.max_age_ms < 0:
        parser.error("Maximum age cannot be negative")

    database = Path(args.database).resolve()

    if not database.is_file():
        parser.error(f"Database not found: {database}")

    with sqlite3.connect(
        database.as_uri() + "?mode=ro",
        uri=True,
    ) as connection:
        connection.row_factory = sqlite3.Row

        trades = connection.execute(
            """
            SELECT asset, trade_timestamp_ms
            FROM spot_trades
            ORDER BY asset, trade_timestamp_ms
            """
        ).fetchall()

        events = connection.execute(
            """
            SELECT
                m.asset,
                b.source_timestamp_ms AS timestamp_ms,
                'book' AS event_type
            FROM order_book_snapshots b
            JOIN outcomes o
                ON o.token_id = b.token_id
            JOIN markets m
                ON m.market_id = o.market_id
            WHERE b.source_timestamp_ms IS NOT NULL

            UNION ALL

            SELECT
                m.asset,
                p.source_timestamp_ms AS timestamp_ms,
                'price_change' AS event_type
            FROM market_price_changes p
            JOIN outcomes o
                ON o.token_id = p.token_id
            JOIN markets m
                ON m.market_id = o.market_id
            WHERE p.source_timestamp_ms IS NOT NULL
            """
        ).fetchall()

    trade_times = {}

    for row in trades:
        trade_times.setdefault(
            row["asset"], []
        ).append(row["trade_timestamp_ms"])

    counts = Counter()
    counts_by_asset = Counter()

    for event in events:
        asset = event["asset"]
        timestamp = event["timestamp_ms"]
        times = trade_times.get(asset, [])

        if not times:
            status = "no_spot_history"

        elif timestamp < times[0]:
            status = "before_spot_history"

        elif timestamp > times[-1]:
            position = len(times) - 1
            age = timestamp - times[position]

            status = (
                "matched"
                if age <= args.max_age_ms
                else "after_spot_history"
            )

        else:
            position = bisect_right(
                times, timestamp
            ) - 1

            age = timestamp - times[position]

            status = (
                "matched"
                if age <= args.max_age_ms
                else "stale_spot"
            )

        counts[status] += 1
        counts_by_asset[(asset, status)] += 1

    print("\nCROSS-MARKET COVERAGE REPORT")
    print("=" * 60)

    print(f"Registered market events: {len(events)}")
    print(f"Maximum spot age: {args.max_age_ms} ms")

    for status in (
        "matched",
        "before_spot_history",
        "after_spot_history",
        "stale_spot",
        "no_spot_history",
    ):
        print(f"{status}: {counts[status]}")

    print("\nASSET BREAKDOWN")
    print("=" * 60)

    for asset in sorted(trade_times):
        times = trade_times[asset]

        print(f"\n{asset}")
        print(f"First trade: {utc_time(times[0])}")
        print(f"Last trade:  {utc_time(times[-1])}")

        for status in (
            "matched",
            "before_spot_history",
            "after_spot_history",
            "stale_spot",
            "no_spot_history",
        ):
            print(
                f"  {status}: "
                f"{counts_by_asset[(asset, status)]}"
            )


if __name__ == "__main__":
    main()
