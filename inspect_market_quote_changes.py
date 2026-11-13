

import sqlite3
from collections import Counter, defaultdict
from pathlib import Path


DATABASE = Path("data/prediction_markets.db")


def main():
    if not DATABASE.is_file():
        raise FileNotFoundError(DATABASE)

    with sqlite3.connect(
        DATABASE.resolve().as_uri() + "?mode=ro",
        uri=True,
    ) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT
                p.token_id,
                o.outcome_name,
                m.asset,
                p.source_timestamp_ms,
                p.observed_at_utc,
                p.best_bid,
                p.best_ask
            FROM market_price_changes p
            LEFT JOIN outcomes o
                ON o.token_id = p.token_id
            LEFT JOIN markets m
                ON m.market_id = o.market_id
            WHERE p.source_timestamp_ms IS NOT NULL
            ORDER BY
                p.token_id,
                p.source_timestamp_ms,
                p.id
            """
        ).fetchall()

    by_token = defaultdict(list)

    for row in rows:
        by_token[row["token_id"]].append(row)

    print("\nPOLYMARKET QUOTE MOVEMENT AUDIT")
    print("=" * 60)
    print(f"Timestamped price-change records: {len(rows)}")
    print(f"Distinct tokens: {len(by_token)}")

    for token_id, events in by_token.items():
        quote_pairs = [
            (event["best_bid"], event["best_ask"])
            for event in events
        ]

        changes = sum(
            previous != current
            for previous, current in zip(
                quote_pairs,
                quote_pairs[1:],
            )
        )

        print("\n" + "-" * 60)
        print(f"Token: {token_id[:20]}...")
        print(f"Asset: {events[0]['asset']}")
        print(f"Outcome: {events[0]['outcome_name']}")
        print(f"Records: {len(events)}")
        print(f"Distinct quote pairs: {len(set(quote_pairs))}")
        print(f"Quote transitions: {changes}")

        print("Most common quote pairs:")

        for quote, count in Counter(
            quote_pairs
        ).most_common(5):
            print(f"  {quote}: {count}")

        print("First event:")
        print(
            events[0]["source_timestamp_ms"],
            quote_pairs[0],
        )

        print("Last event:")
        print(
            events[-1]["source_timestamp_ms"],
            quote_pairs[-1],
        )


if __name__ == "__main__":
    main()
