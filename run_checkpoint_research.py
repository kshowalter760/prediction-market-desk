
import argparse
import csv
import sqlite3
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from prediction_desk.checkpoint_quality import (
    audit_checkpoint_quality,
)
from prediction_desk.checkpoint_research import (
    build_checkpoint_research,
)

from prediction_desk.checkpoint_statistics import (
    summarize_token,
)
from prediction_desk.checkpoint_verification_coverage import (
    evaluate_checkpoint_coverage,
)
from prediction_desk.cross_market_alignment import (
    align_checkpoints,
)
from prediction_desk.replay_checkpoints import (
    reconstruct_checkpoints,
)
from prediction_desk.snapshot_pair_report import (
    verify_session_snapshot_pairs,
)


DATABASE = Path("data/prediction_markets.db")
OUTPUT_DIR = Path("reports")


def build_verification_evidence(
    connection,
    session_id,
    rows,
):
    """
    Build snapshot-pair verification and checkpoint coverage.

    Snapshot-pair verification is always evaluated.

    Coverage is unavailable when there are no research rows,
    because an empty dataset has no checkpoints to classify.
    """
    verification_report = verify_session_snapshot_pairs(
        connection,
        session_id,
    )

    coverage_report = None

    if rows:
        coverage_report = evaluate_checkpoint_coverage(
            connection,
            rows,
            verification_report,
        )

    return verification_report, coverage_report


def print_snapshot_pair_report(report):
    print()
    print("SNAPSHOT-PAIR VERIFICATION")
    print("=" * 75)

    print("Session:", report.session_id)
    print("Snapshots:", report.snapshot_count)
    print("Tokens:", report.token_count)
    print("Candidate pairs:", report.eligible_pair_count)
    print("Matched:", report.matched_pair_count)
    print("Mismatched:", report.mismatched_pair_count)
    print("Errors:", report.error_count)

    for pair in report.results:
        print(
            f"PAIR={pair.initial_snapshot_id}"
            f"->{pair.final_snapshot_id} "
            f"TOKEN={pair.token_id[:12]}... "
            f"STATUS={pair.status} "
            f"UPDATES={pair.updates_applied}"
        )

        if pair.error:
            print("PAIR ERROR:", pair.error)


def main():
    parser = argparse.ArgumentParser(
        description="Build historical checkpoint research dataset"
    )

    parser.add_argument(
        "--session-id",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--asset",
        choices=("BTC", "ETH"),
        default="BTC",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=30,
    )

    parser.add_argument(
        "--max-spot-age-ms",
        type=int,
        default=5000,
    )

    args = parser.parse_args()

    if args.session_id <= 0:
        parser.error("--session-id must be positive")

    if args.interval <= 0:
        parser.error("--interval must be positive")

    if args.max_spot_age_ms < 0:
        parser.error("--max-spot-age-ms cannot be negative")

    if not DATABASE.is_file():
        raise FileNotFoundError(
            f"Database not found: {DATABASE}"
        )

    uri = f"file:{DATABASE.resolve().as_posix()}?mode=ro"

    # Historical research and verification use a read-only database.
    with sqlite3.connect(uri, uri=True) as connection:
        snapshots = connection.execute(
            """
            SELECT id
            FROM order_book_snapshots
            WHERE stream_session_id = ?
            ORDER BY id
            """,
            (args.session_id,),
        ).fetchall()

        observations = []

        for (snapshot_id,) in snapshots:
            checkpoints = reconstruct_checkpoints(
                connection,
                snapshot_id,
                interval_ms=args.interval * 1000,
            )

            observations.extend(
                align_checkpoints(
                    connection,
                    checkpoints,
                    asset=args.asset,
                    max_spot_age_ms=args.max_spot_age_ms,
                )
            )

        rows = build_checkpoint_research(observations)

        # Verification evidence is derived from the same database
        # and session as the research observations.
        verification_report, coverage_report = (
            build_verification_evidence(
                connection,
                args.session_id,
                rows,
            )
        )

    print()
    print("HISTORICAL CHECKPOINT RESEARCH")
    print("=" * 75)
    print("Session:", args.session_id)
    print("Asset:", args.asset)
    print("Rows:", len(rows))
    print(
        "Unique timestamps:",
        len({row.timestamp_ms for row in rows}),
    )

    counts = Counter(
        row.alignment_status for row in rows
    )

    print("Aligned:", counts["aligned"])
    print("Stale:", counts["stale_spot"])
    print("Missing:", counts["missing_spot"])

    for row in rows:
        print(
            f"TOKEN={row.token_id[:12]}... "
            f"TIME={row.timestamp_ms} "
            f"SPOT={row.spot_price_usd} "
            f"RETURN_PCT={row.spot_return_pct} "
            f"POLY_MID={row.polymarket_mid_price} "
            f"MID_CHANGE={row.polymarket_mid_change}"
        )

    if not rows:
        print("No research rows available.")
        return

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = OUTPUT_DIR / (
        f"checkpoint_research_session_{args.session_id}_"
        f"{args.asset.lower()}_{args.interval}s_"
        f"{args.max_spot_age_ms}ms.csv"
    )

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(asdict(rows[0]).keys()),
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(asdict(row))

    print()
    print("CSV exported:", output_path)
    print(
        "Note: Exploratory event-time research data; "
        "not independently verified live-available history."
    )

    print()
    print("CHECKPOINT STATISTICAL ANALYSIS")
    print("=" * 75)

    token_ids = sorted({
        row.token_id for row in rows
    })

    for token_id in token_ids:
        token_rows = [
            row for row in rows
            if row.token_id == token_id
        ]

        stats = summarize_token(token_rows)

        print()
        print("-" * 75)
        print(f"Token: {token_id[:20]}...")
        print(f"Checkpoints: {stats.checkpoint_count}")
        print(f"Aligned: {stats.aligned_count}")
        print(f"Spot returns: {stats.spot_return_count}")
        print(
            "Midpoint changes observed:",
            stats.midpoint_change_count,
        )
        print(
            "Nonzero midpoint changes:",
            stats.midpoint_change_events,
        )
        print(
            "Average absolute BTC return (%):",
            stats.average_absolute_spot_return_pct,
        )
        print(
            "Maximum absolute BTC return (%):",
            stats.maximum_absolute_spot_return_pct,
        )
        print(
            "Average absolute midpoint change:",
            stats.average_absolute_midpoint_change,
        )
        print(
            "Correlation:",
            stats.correlation,
        )
        print(
            "Correlation status:",
            stats.correlation_status,
        )

    print()
    print("SNAPSHOT-PAIR VERIFICATION")
    print("=" * 75)

    print(
        "Session:",
        verification_report.session_id,
    )
    print(
        "Snapshots:",
        verification_report.snapshot_count,
    )
    print(
        "Tokens:",
        verification_report.token_count,
    )
    print(
        "Candidate pairs:",
        verification_report.eligible_pair_count,
    )
    print(
        "Matched:",
        verification_report.matched_pair_count,
    )
    print(
        "Mismatched:",
        verification_report.mismatched_pair_count,
    )
    print(
        "Errors:",
        verification_report.error_count,
    )

    for pair in verification_report.results:
        print(
            f"PAIR={pair.initial_snapshot_id}"
            f"->{pair.final_snapshot_id} "
            f"TOKEN={pair.token_id[:12]}... "
            f"STATUS={pair.status} "
            f"UPDATES={pair.updates_applied}"
        )

        if pair.error:
            print("PAIR ERROR:", pair.error)

    print()
    print("CHECKPOINT VERIFICATION COVERAGE")
    print("=" * 75)

    print(
        "Research checkpoints:",
        coverage_report.checkpoint_count,
    )
    print(
        "Covered checkpoints:",
        coverage_report.covered_count,
    )
    print(
        "Uncovered checkpoints:",
        coverage_report.uncovered_count,
    )
    print(
        "All checkpoints covered:",
        coverage_report.all_checkpoints_covered,
    )

    for checkpoint in coverage_report.checkpoints:
        print(
            f"TOKEN={checkpoint.token_id[:12]}... "
            f"TIME={checkpoint.timestamp_ms} "
            f"SEQ={checkpoint.message_sequence} "
            f"COVERED={checkpoint.covered} "
            f"INITIAL={checkpoint.initial_snapshot_id} "
            f"FINAL={checkpoint.final_snapshot_id}"
        )

    print()
    print(
        "Verification interpretation: coverage means that a "
        "checkpoint falls within a matched snapshot-pair interval."
    )
    print(
        "Matched endpoints do not independently verify every "
        "intermediate reconstructed checkpoint."
    )

    if coverage_report.uncovered_count:
        print(
            "WARNING: Some research checkpoints have no "
            "matched snapshot-pair interval coverage."
        )

    print()
    print("RESEARCH LIMITATIONS")
    print("=" * 75)

    print("- Event-time alignment only.")
    print("- Checkpoint intervals are not exactly uniform.")
    print("- Complementary outcomes are not independent samples.")
    print(
        "- Matched snapshot endpoints do not establish "
        "intermediate checkpoint correctness."
    )
    print(
        "- Stream completeness and live information "
        "availability are not established."
    )
    print("- No predictive relationship is established.")

    # Conservative quality gate:
    # interval coverage is not sufficient to establish
    # independent intermediate checkpoint verification.
    quality = audit_checkpoint_quality(
        rows,
        expected_interval_ms=args.interval * 1000,
        independent_replay_verified=False,
    )

    print()
    print("HISTORICAL DATA QUALITY AUDIT")
    print("=" * 75)

    print("Unique timestamps:", quality.unique_timestamps)
    print("Tokens:", quality.token_count)
    print("Aligned:", quality.aligned_count)
    print("Stale:", quality.stale_count)
    print("Missing:", quality.missing_count)
    print(
        "Minimum interval (ms):",
        quality.minimum_interval_ms,
    )
    print(
        "Maximum interval (ms):",
        quality.maximum_interval_ms,
    )
    print(
        "Maximum spot age (ms):",
        quality.maximum_spot_age_ms,
    )
    print("Long checkpoint gaps:", quality.long_gap_count)
    print(
        "Independent replay verified:",
        quality.independent_replay_verified,
    )
    print("Research ready:", quality.research_ready)

    for warning in quality.warnings:
        print("WARNING:", warning)


if __name__ == "__main__":
    main()

