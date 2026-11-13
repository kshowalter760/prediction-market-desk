
import argparse
import sqlite3

from prediction_desk.snapshot_pair_report import (
    verify_session_snapshot_pairs,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", type=int, required=True)
    parser.add_argument(
        "--database",
        default="data/prediction_markets.db",
    )

    args = parser.parse_args()

    connection = sqlite3.connect(
        f"file:{args.database}?mode=ro",
        uri=True,
    )

    try:
        report = verify_session_snapshot_pairs(
            connection,
            args.session_id,
        )
    finally:
        connection.close()

    print()
    print("SNAPSHOT-PAIR VERIFICATION REPORT")
    print("=" * 75)
    print("Session:", report.session_id)
    print("Snapshots:", report.snapshot_count)
    print("Tokens:", report.token_count)
    print("Candidate pairs:", report.eligible_pair_count)
    print("Matched:", report.matched_pair_count)
    print("Mismatched:", report.mismatched_pair_count)
    print("Errors:", report.error_count)

    for result in report.results:
        print()
        print(
            f"SNAPSHOTS={result.initial_snapshot_id}"
            f"->{result.final_snapshot_id}"
        )
        print("Token:", result.token_id[:20])
        print("Status:", result.status)
        print("Updates:", result.updates_applied)

        if result.error:
            print("Error:", result.error)

    if report.eligible_pair_count == 0:
        print()
        print("No eligible snapshot pairs found.")
        print("Independent replay verification unavailable.")

    print()
    print(
        "Note: Matching recorded depth does not prove "
        "stream completeness or live data availability."
    )

    # Checkpoint coverage requires research rows from the
    # corresponding session. We will integrate this into
    # run_checkpoint_research.py after unit testing.


if __name__ == "__main__":
    main()

