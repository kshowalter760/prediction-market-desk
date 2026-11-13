
import json
from pathlib import Path

from prediction_desk.reports import build_research_report
from prediction_desk.storage import Storage


DATABASE_PATH = Path("data/prediction_markets.db")
REPORT_PATH = Path("reports/market_shocks.json")


def main():
    with Storage(DATABASE_PATH) as storage:
        storage.initialize()
        report = build_research_report(storage)

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\nResearch report generated")
    print(f"Report: {REPORT_PATH}")
    print(f"Events: {report['event_count']}")

    for event in report["events"]:
        print(
            f"\n{event['asset']} | "
            f"Market {event['market_id']}"
        )
        print(
            f"Magnitude: "
            f"{event['magnitude_percentage_points']} pp"
        )
        print(
            f"Evidence: "
            f"{event['evidence_classification']}"
        )
        print(
            f"Supporting outcomes: "
            f"{event['supporting_outcome_count']}"
        )


if __name__ == "__main__":
    main()
