
import json
from datetime import datetime, timezone
from decimal import Decimal


def classify_evidence(outcomes):
    if not isinstance(outcomes, list):
        raise ValueError("outcomes must be a list")

    if len(outcomes) != 2:
        return "single_or_unpaired"

    names = {
        outcome.get("outcome_name")
        for outcome in outcomes
    }

    if names != {"Up", "Down"}:
        return "single_or_unpaired"

    try:
        changes = [
            Decimal(str(outcome["change"]))
            for outcome in outcomes
        ]
    except (KeyError, TypeError, ValueError):
        return "single_or_unpaired"

    if not all(change.is_finite() for change in changes):
        return "single_or_unpaired"

    if changes[0] * changes[1] >= 0:
        return "single_or_unpaired"

    return "complementary_outcomes"


def build_research_report(storage):
    rows = storage.connection.execute(
        """
        SELECT
            s.market_id,
            m.asset,
            m.market_type,
            m.question,
            m.end_date,
            s.event_timestamp_ms,
            s.magnitude,
            s.outcome_details_json,
            s.detected_at_utc
        FROM market_shocks AS s
        JOIN markets AS m
            ON s.market_id = m.market_id
        ORDER BY
            s.event_timestamp_ms DESC,
            s.id DESC
        """
    ).fetchall()

    events = []

    for row in rows:
        (
            market_id,
            asset,
            market_type,
            question,
            end_date,
            timestamp_ms,
            magnitude,
            details_json,
            detected_at_utc,
        ) = row

        outcomes = json.loads(details_json)

        events.append({
            "market_id": market_id,
            "asset": asset,
            "market_type": market_type,
            "question": question,
            "market_end_date": end_date,
            "event_timestamp_ms": timestamp_ms,
            "magnitude": magnitude,
            "magnitude_percentage_points": str(
                Decimal(magnitude) * 100
            ),
            "detected_at_utc": detected_at_utc,
            "evidence_classification": (
                classify_evidence(outcomes)
            ),
            "supporting_outcome_count": len(outcomes),
            "supporting_outcomes": outcomes,
        })

    return {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "event_count": len(events),
        "events": events,
    }
