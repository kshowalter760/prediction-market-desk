
from dataclasses import dataclass

from prediction_desk.checkpoint_research import (
    CheckpointResearchRow,
)
from prediction_desk.snapshot_pair_report import (
    SessionVerificationReport,
)


@dataclass(frozen=True)
class CheckpointCoverage:
    token_id: str
    timestamp_ms: int
    message_sequence: int
    covered: bool
    initial_snapshot_id: int | None
    final_snapshot_id: int | None


@dataclass(frozen=True)
class CoverageReport:
    session_id: int
    checkpoint_count: int
    covered_count: int
    uncovered_count: int
    all_checkpoints_covered: bool
    checkpoints: tuple[CheckpointCoverage, ...]


def evaluate_checkpoint_coverage(
    connection,
    rows: list[CheckpointResearchRow],
    verification_report: SessionVerificationReport,
) -> CoverageReport:

    if not rows:
        raise ValueError("Cannot evaluate empty checkpoint dataset")

    session_ids = {row.session_id for row in rows}

    if session_ids != {verification_report.session_id}:
        raise ValueError("Session mismatch")

    # Use only independently matching snapshot pairs.
    matched_pairs = [
        result
        for result in verification_report.results
        if result.status == "matched"
    ]

    snapshot_ids = {
        snapshot_id
        for pair in matched_pairs
        for snapshot_id in (
            pair.initial_snapshot_id,
            pair.final_snapshot_id,
        )
    }

    metadata = {}

    for snapshot_id in snapshot_ids:
        record = connection.execute(
            """
            SELECT
                token_id,
                stream_session_id,
                message_sequence,
                source_timestamp_ms
            FROM order_book_snapshots
            WHERE id = ?
            """,
            (snapshot_id,),
        ).fetchone()

        if record is None:
            raise ValueError("Verification snapshot not found")

        metadata[snapshot_id] = record

    intervals = []

    for pair in matched_pairs:
        initial = metadata[pair.initial_snapshot_id]
        final = metadata[pair.final_snapshot_id]

        initial_token, initial_session, initial_seq, initial_ms = initial
        final_token, final_session, final_seq, final_ms = final

        if (
            initial_token != pair.token_id
            or final_token != pair.token_id
            or initial_session != verification_report.session_id
            or final_session != verification_report.session_id
            or initial_seq is None
            or final_seq is None
            or initial_seq >= final_seq
            or initial_ms > final_ms
        ):
            raise ValueError("Invalid verification interval")

        intervals.append(
            (
                pair.token_id,
                initial_seq,
                final_seq,
                initial_ms,
                final_ms,
                pair.initial_snapshot_id,
                pair.final_snapshot_id,
            )
        )

    checkpoints = []

    for row in rows:
        covering_pair = None

        for (
            token,
            start_seq,
            end_seq,
            start_ms,
            end_ms,
            start_id,
            end_id,
        ) in intervals:
            if (
                row.token_id == token
                and type(row.message_sequence) is int
                and start_seq <= row.message_sequence <= end_seq
                and start_ms <= row.timestamp_ms <= end_ms
            ):
                covering_pair = (start_id, end_id)
                break

        checkpoints.append(
            CheckpointCoverage(
                token_id=row.token_id,
                timestamp_ms=row.timestamp_ms,
                message_sequence=row.message_sequence,
                covered=covering_pair is not None,
                initial_snapshot_id=(
                    covering_pair[0] if covering_pair else None
                ),
                final_snapshot_id=(
                    covering_pair[1] if covering_pair else None
                ),
            )
        )

    covered_count = sum(item.covered for item in checkpoints)

    return CoverageReport(
        session_id=verification_report.session_id,
        checkpoint_count=len(checkpoints),
        covered_count=covered_count,
        uncovered_count=len(checkpoints) - covered_count,
        all_checkpoints_covered=(
            covered_count == len(checkpoints)
        ),
        checkpoints=tuple(checkpoints),
    )
