
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from prediction_desk.cross_market_dataset import (
    build_cross_market_dataset,
)


DATABASE = Path("data/prediction_markets.db")


def parse_utc(value):
    if value is None:
        return None

    timestamp = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    if timestamp.tzinfo is None:
        raise ValueError("Expected timezone-aware timestamp")

    return timestamp.astimezone(timezone.utc)


def main():
    if not DATABASE.is_file():
        raise FileNotFoundError(DATABASE)

    with sqlite3.connect(
        DATABASE.resolve().as_uri() + "?mode=ro",
        uri=True,
    ) as connection:
        rows = build_cross_market_dataset(
            connection,
            max_age_ms=5000,
        )

    matched = [
        row for row in rows
        if row.status == "matched"
    ]

    unique_event_times = {
        (row.asset, row.event_timestamp_ms)
        for row in matched
    }

    unique_spot_trades = {
        (row.asset, row.spot_trade_id)
        for row in matched
    }

    event_types = Counter(
        row.event_type for row in matched
    )

    # Evaluate changes separately for each outcome token.
    by_token = defaultdict(list)

    for row in matched:
        if row.midpoint is not None:
            by_token[row.token_id].append(row)

    midpoint_changes = 0
    unchanged_midpoints = 0

    for token_rows in by_token.values():
        token_rows.sort(
            key=lambda row: (
                row.event_timestamp_ms,
                row.polymarket_observed_at_utc,
            )
        )

        previous_midpoint = None

        for row in token_rows:
            if previous_midpoint is not None:
                if row.midpoint != previous_midpoint:
                    midpoint_changes += 1
                else:
                    unchanged_midpoints += 1

            previous_midpoint = row.midpoint

    received_before = 0
    received_after = 0
    missing_observation_time = 0

    for row in matched:
        spot_received = parse_utc(
            row.spot_observed_at_utc
        )

        market_received = parse_utc(
            row.polymarket_observed_at_utc
        )

        if spot_received is None or market_received is None:
            missing_observation_time += 1

        elif spot_received <= market_received:
            received_before += 1

        else:
            received_after += 1

    print("\nSIGNAL QUALITY AUDIT")
    print("=" * 60)

    print(f"Total observations: {len(rows)}")
    print(f"Matched observations: {len(matched)}")
    print(f"Unique source-time events: {len(unique_event_times)}")
    print(f"Unique Coinbase trades used: {len(unique_spot_trades)}")

    print("\nEVENT TYPES")
    print("=" * 60)

    for event_type, count in sorted(event_types.items()):
        print(f"{event_type}: {count}")

    print("\nMIDPOINT BEHAVIOR")
    print("=" * 60)

    print(f"Changed midpoint: {midpoint_changes}")
    print(f"Unchanged midpoint: {unchanged_midpoints}")

    print("\nOBSERVATION-TIME AVAILABILITY")
    print("=" * 60)

    print(f"Spot received first or simultaneously: {received_before}")
    print(f"Spot received afterward: {received_after}")
    print(f"Missing receipt timestamp: {missing_observation_time}")

    print("\nNOTE")
    print(
        "Receipt-time ordering is a necessary check, "
        "not proof of executable trading opportunities."
    )


if __name__ == "__main__":
    main()
