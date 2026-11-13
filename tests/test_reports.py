
import json

from prediction_desk.reports import (
    build_research_report,
    classify_evidence,
)
from prediction_desk.storage import Storage


def test_classifies_complementary_outcomes():
    outcomes = [
        {"outcome_name": "Up", "change": "-0.23"},
        {"outcome_name": "Down", "change": "0.23"},
    ]

    assert classify_evidence(outcomes) == (
        "complementary_outcomes"
    )


def test_classifies_single_outcome():
    outcomes = [
        {"outcome_name": "Up", "change": "-0.23"},
    ]

    assert classify_evidence(outcomes) == (
        "single_or_unpaired"
    )


def test_rejects_same_direction_as_confirmation():
    outcomes = [
        {"outcome_name": "Up", "change": "0.23"},
        {"outcome_name": "Down", "change": "0.23"},
    ]

    assert classify_evidence(outcomes) == (
        "single_or_unpaired"
    )


def test_empty_database_report(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()
        report = build_research_report(storage)

    assert report["schema_version"] == "1.0"
    assert report["event_count"] == 0
    assert report["events"] == []


def test_report_contains_stored_event(tmp_path):
    with Storage(tmp_path / "test.db") as storage:
        storage.initialize()

        with storage.connection:
            storage.connection.execute(
                """
                INSERT INTO markets (
                    market_id,
                    event_title,
                    question,
                    asset,
                    market_type,
                    condition_id,
                    end_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "100",
                    "Bitcoin Up or Down",
                    "Bitcoin Up or Down",
                    "BTC",
                    "directional",
                    "0xabc",
                    "2026-12-31T23:59:00Z",
                ),
            )

            storage.connection.execute(
                """
                INSERT INTO market_shocks (
                    market_id,
                    event_timestamp_ms,
                    magnitude,
                    outcome_details_json,
                    detected_at_utc
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "100",
                    120000,
                    "0.23",
                    json.dumps([
                        {
                            "outcome_name": "Up",
                            "change": "-0.23",
                        },
                        {
                            "outcome_name": "Down",
                            "change": "0.23",
                        },
                    ]),
                    "2026-10-26T00:00:00+00:00",
                ),
            )

        report = build_research_report(storage)

    assert report["event_count"] == 1

    event = report["events"][0]

    assert event["market_id"] == "100"
    assert event["asset"] == "BTC"
    assert event["magnitude_percentage_points"] == "23.00"
    assert event["supporting_outcome_count"] == 2
    assert event["evidence_classification"] == (
        "complementary_outcomes"
    )
