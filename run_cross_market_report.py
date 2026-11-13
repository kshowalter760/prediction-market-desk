
import argparse
from collections import Counter
from pathlib import Path
import sqlite3

from prediction_desk.cross_market_dataset import (
    build_cross_market_dataset,
)


def main():
    parser = argparse.ArgumentParser(
        description="Cross-market alignment report"
    )

    parser.add_argument(
        "--database",
        default="data/prediction_markets.db",
    )

    parser.add_argument(
        "--max-age-ms",
        type=int,
        default=5000,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
    )

    args = parser.parse_args()

    if args.limit < 0 or args.max_age_ms < 0:
        parser.error(
            "Limit and maximum age must be nonnegative"
        )

    database = Path(args.database).resolve()

    if not database.is_file():
        parser.error(f"Database not found: {database}")

    uri = database.as_uri() + "?mode=ro"

    with sqlite3.connect(uri, uri=True) as connection:
        rows = build_cross_market_dataset(
            connection,
            max_age_ms=args.max_age_ms,
        )

    counts = Counter(row.status for row in rows)

    print("\nCROSS-MARKET RESEARCH REPORT")
    print("=" * 60)

    print(f"Eligible observations: {len(rows)}")
    print(f"Maximum spot age: {args.max_age_ms} ms")

    print(f"Matched: {counts['matched']}")
    print(f"Stale: {counts['stale_spot']}")
    print(f"No prior spot: {counts['no_prior_spot']}")

    print("\nRECENT OBSERVATIONS")
    print("=" * 60)

    selected = rows[-args.limit:] if args.limit else []

    for row in selected:
        print(
            f"\n{row.asset} / {row.outcome_name}"
            f" / {row.event_type}"
        )
        print(f"Event time: {row.event_timestamp_ms}")
        print(f"Bid: {row.best_bid}")
        print(f"Ask: {row.best_ask}")
        print(f"Midpoint: {row.midpoint}")
        print(f"Spot price: {row.spot_price_usd}")
        print(f"Spot age: {row.spot_age_ms} ms")
        print(f"Alignment: {row.status}")


if __name__ == "__main__":
    main()
