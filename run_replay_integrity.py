
import argparse
import json
import sqlite3
from pathlib import Path

from prediction_desk.replay_integrity import (
    audit_session,
    results_to_dicts,
)


DATABASE = Path("data/prediction_markets.db")


def main():
    parser = argparse.ArgumentParser(
        description="Audit historical order-book replay integrity"
    )
    parser.add_argument(
        "--session-id",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )

    args = parser.parse_args()

    if not DATABASE.is_file():
        raise FileNotFoundError(DATABASE)

    uri = f"file:{DATABASE.resolve().as_posix()}?mode=ro"

    with sqlite3.connect(uri, uri=True) as connection:
        session_id = args.session_id

        if session_id is None:
            row = connection.execute(
                """
                SELECT id
                FROM polymarket_stream_sessions
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "No Polymarket stream sessions found"
                )

            session_id = row[0]

        results = audit_session(connection, session_id)

    print()
    print("HISTORICAL REPLAY INTEGRITY REPORT")
    print("=" * 70)
    print("Session:", session_id)
    print("Replay windows:", len(results))

    for result in results:
        status = (
            "EXACT MATCH"
            if result.exact_match
            else "MISMATCH"
        )

        print(
            f"{result.start_snapshot_id} -> "
            f"{result.end_snapshot_id} | "
            f"updates={result.updates_applied}/"
            f"{result.updates_selected} | "
            f"bid_diff={result.bid_differences} | "
            f"ask_diff={result.ask_differences} | "
            f"{status}"
        )

        if result.error:
            print("  Error:", result.error)

    matches = sum(result.exact_match for result in results)

    print()
    print("Exact matches:", matches)
    print("Mismatches:", len(results) - matches)

    if not results:
        print(
            "No consecutive snapshot pairs were found. "
            "Integrity is not verified."
        )

    if args.output is not None:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        args.output.write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "replay_windows": len(results),
                    "exact_matches": matches,
                    "results": results_to_dicts(results),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        print("Report saved:", args.output)


if __name__ == "__main__":
    main()
