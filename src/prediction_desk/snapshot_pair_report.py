
from dataclasses import dataclass

from prediction_desk.snapshot_pair_verification import (
    verify_snapshot_pair,
)


@dataclass(frozen=True)
class PairResult:
    initial_snapshot_id: int
    final_snapshot_id: int
    token_id: str
    session_id: int
    status: str
    updates_applied: int | None
    error: str | None


@dataclass(frozen=True)
class SessionVerificationReport:
    session_id: int
    snapshot_count: int
    token_count: int
    eligible_pair_count: int
    matched_pair_count: int
    mismatched_pair_count: int
    error_count: int
    results: tuple[PairResult, ...]


def verify_session_snapshot_pairs(
    connection,
    session_id: int,
    *,
    max_updates: int = 100_000,
) -> SessionVerificationReport:

    if type(session_id) is not int or session_id <= 0:
        raise ValueError("Invalid session ID")

    if type(max_updates) is not int or max_updates <= 0:
        raise ValueError("max_updates must be positive")

    snapshots = connection.execute(
        """
        SELECT
            id,
            token_id,
            message_sequence
        FROM order_book_snapshots
        WHERE stream_session_id = ?
        ORDER BY token_id, message_sequence, id
        """,
        (session_id,),
    ).fetchall()

    grouped = {}

    for snapshot_id, token_id, sequence in snapshots:
        grouped.setdefault(token_id, []).append(
            (snapshot_id, sequence)
        )

    results = []

    for token_id, token_snapshots in grouped.items():
        for initial, final in zip(
            token_snapshots,
            token_snapshots[1:],
        ):
            initial_id, initial_seq = initial
            final_id, final_seq = final

            if (
                initial_seq is None
                or final_seq is None
                or final_seq <= initial_seq
            ):
                results.append(
                    PairResult(
                        initial_snapshot_id=initial_id,
                        final_snapshot_id=final_id,
                        token_id=token_id,
                        session_id=session_id,
                        status="invalid_sequence",
                        updates_applied=None,
                        error="Missing or non-increasing sequence",
                    )
                )
                continue

            try:
                verification = verify_snapshot_pair(
                    connection,
                    initial_id,
                    final_id,
                    max_updates=max_updates,
                )

                status = (
                    "matched"
                    if verification.independently_verified
                    else "mismatched"
                )

                results.append(
                    PairResult(
                        initial_snapshot_id=initial_id,
                        final_snapshot_id=final_id,
                        token_id=token_id,
                        session_id=session_id,
                        status=status,
                        updates_applied=verification.updates_applied,
                        error=None,
                    )
                )

            except (ValueError, ArithmeticError) as exc:
                results.append(
                    PairResult(
                        initial_snapshot_id=initial_id,
                        final_snapshot_id=final_id,
                        token_id=token_id,
                        session_id=session_id,
                        status="error",
                        updates_applied=None,
                        error=str(exc),
                    )
                )

    return SessionVerificationReport(
        session_id=session_id,
        snapshot_count=len(snapshots),
        token_count=len(grouped),
        eligible_pair_count=len(results),
        matched_pair_count=sum(
            item.status == "matched" for item in results
        ),
        mismatched_pair_count=sum(
            item.status == "mismatched" for item in results
        ),
        error_count=sum(
            item.status in ("error", "invalid_sequence")
            for item in results
        ),
        results=tuple(results),
    )
