
import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from prediction_desk.cross_market import (
    assess_cross_market_event,
)
from prediction_desk.spot import (
    CoinbaseSpotClient,
    SpotAPIError,
)
from prediction_desk.storage import Storage


DATABASE_PATH = Path("data/prediction_markets.db")
REPORT_PATH = Path("reports/cross_market.json")


def utc_from_ms(timestamp_ms):
    return datetime.fromtimestamp(
        timestamp_ms / 1000,
        tz=timezone.utc,
    )


def main():
    with Storage(DATABASE_PATH) as storage:
        storage.initialize()

        rows = storage.connection.execute(
            """
            SELECT
                s.market_id,
                m.asset,
                s.outcome_details_json
            FROM market_shocks AS s
            JOIN markets AS m
                ON s.market_id = m.market_id
            ORDER BY s.event_timestamp_ms
            """
        ).fetchall()

    assessments = []
    failures = []

    with CoinbaseSpotClient() as client:
        for market_id, asset, details_json in rows:
            outcomes = json.loads(details_json)

            if not outcomes:
                continue

            # Use the first supporting outcome.
            # Its sign refers to that specific outcome.
            outcome = outcomes[0]

            previous_ms = outcome[
                "previous_timestamp_ms"
            ]
            current_ms = outcome[
                "current_timestamp_ms"
            ]

            start = utc_from_ms(
                previous_ms
            ) - timedelta(minutes=3)

            end = utc_from_ms(
                current_ms
            ) + timedelta(minutes=1)

            # Coinbase limits each request to 300 candles.
            # Keep the first implementation bounded.
            if end - start > timedelta(minutes=300):
                failures.append(
                    f"{market_id}: window exceeds 300 minutes"
                )
                continue

            try:
                candles = client.get_historical_candles(
                    asset=asset,
                    start=start,
                    end=end,
                )
            except SpotAPIError as exc:
                failures.append(
                    f"{market_id}: {exc}"
                )
                continue

            assessment = assess_cross_market_event(
                asset=asset,
                market_id=market_id,
                previous_timestamp_ms=previous_ms,
                current_timestamp_ms=current_ms,
                probability_change=Decimal(
                    outcome["change"]
                ),
                candles=candles,
            )

            result = asdict(assessment)

            # Convert Decimal values for JSON.
            for key in (
                "probability_change",
                "spot_return",
                "spot_change_usd",
            ):
                if result[key] is not None:
                    result[key] = str(result[key])

            result["reference_outcome"] = outcome[
                "outcome_name"
            ]

            assessments.append(result)

    report = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "assessments": assessments,
        "failures": failures,
    }

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_PATH.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("\nCross-market research report")
    print(f"Assessments: {len(assessments)}")
    print(f"Retrieval failures: {len(failures)}")

    for result in assessments:
        print(
            f"\n{result['asset']} | "
            f"Market {result['market_id']}"
        )
        print(f"Status: {result['status']}")
        print(
            f"Reference outcome: "
            f"{result['reference_outcome']}"
        )
        print(
            f"Probability change: "
            f"{Decimal(result['probability_change']) * 100} pp"
        )
        print(
            f"Spot return: {result['spot_return']}"
        )
        print(result["explanation"])

    for failure in failures:
        print(f"Retrieval failure: {failure}")

    print(f"\nReport: {REPORT_PATH}")


if __name__ == "__main__":
    main()
