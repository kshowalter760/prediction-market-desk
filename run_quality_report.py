
from collections import Counter
from pathlib import Path

from prediction_desk.quality import (
    assess_observation_quality,
)
from prediction_desk.storage import Storage


DATABASE_PATH = Path("data/prediction_markets.db")


def main():
    with Storage(DATABASE_PATH) as storage:
        storage.initialize()

        rows = storage.connection.execute(
            """
            SELECT
                token_id,
                source_timestamp_ms,
                observed_at_utc
            FROM order_book_snapshots
            ORDER BY source_timestamp_ms DESC
            """
        ).fetchall()

    counts = Counter()
    lags = []

    for token_id, source_ms, observed_at in rows:
        result = assess_observation_quality(
            source_timestamp_ms=source_ms,
            observed_at_utc=observed_at,
        )

        counts[result.status] += 1
        lags.append(result.lag_ms)

    print("\nObservation quality report")
    print(f"Snapshots assessed: {len(rows)}")
    print(f"Fresh: {counts['fresh']}")
    print(f"Stale: {counts['stale']}")
    print(
        f"Future timestamps: "
        f"{counts['future_timestamp']}"
    )

    if lags:
        print(
            f"Minimum lag: {min(lags)} ms"
        )
        print(
            f"Maximum lag: {max(lags)} ms"
        )
        print(
            f"Average lag: "
            f"{sum(lags) / len(lags):.1f} ms"
        )


if __name__ == "__main__":
    main()
