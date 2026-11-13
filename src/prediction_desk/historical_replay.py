
from dataclasses import dataclass
from decimal import Decimal

from prediction_desk.book_reconstruction import (
    BookReconstructor,
    ReconstructionUpdate,
    ReconstructedBook,
)
from prediction_desk.snapshot_reconstruction import (
    reconstruct_snapshot,
)


@dataclass(frozen=True)
class ReplayResult:
    snapshot_id: int
    token_id: str
    initial_state: ReconstructedBook
    final_state: ReconstructedBook
    updates_applied: int
    first_update_ms: int | None
    last_update_ms: int | None
    continuity_verified: bool
    absolute_size_semantics_verified: bool


def replay_from_snapshot(
    connection,
    snapshot_id: int,
    *,
    max_updates: int = 10000,
) -> ReplayResult:
    if type(max_updates) is not int or max_updates <= 0:
        raise ValueError("max_updates must be positive")

    verification = reconstruct_snapshot(
        connection,
        snapshot_id,
    )

    if not verification.matches_metadata:
        raise ValueError(
            "Snapshot metadata does not match persisted depth"
        )

    initial = verification.reconstructed

    engine = BookReconstructor(
        timestamp_ms=initial.timestamp_ms,
        bids=initial.bids,
        asks=initial.asks,
    )

    # Fetch one additional row to detect a truncated replay.
    rows = connection.execute(
        """
        SELECT
            id,
            source_timestamp_ms,
            side,
            price,
            size
        FROM market_level_updates
        WHERE token_id = ?
          AND source_timestamp_ms > ?
        ORDER BY source_timestamp_ms ASC, id ASC
        LIMIT ?
        """,
        (
            verification.token_id,
            initial.timestamp_ms,
            max_updates + 1,
        ),
    ).fetchall()

    if len(rows) > max_updates:
        raise ValueError(
            "Replay exceeds max_updates; refusing partial result"
        )

    first_update_ms = None
    last_update_ms = None

    for (
        row_id,
        timestamp_ms,
        side,
        price,
        size,
    ) in rows:
        if first_update_ms is None:
            first_update_ms = timestamp_ms

        engine.apply(
            ReconstructionUpdate(
                timestamp_ms=timestamp_ms,
                side=side,
                price=Decimal(price),
                size=Decimal(size),
            )
        )

        last_update_ms = timestamp_ms

    return ReplayResult(
        snapshot_id=snapshot_id,
        token_id=verification.token_id,
        initial_state=initial,
        final_state=engine.state(),
        updates_applied=len(rows),
        first_update_ms=first_update_ms,
        last_update_ms=last_update_ms,
        continuity_verified=False,
        absolute_size_semantics_verified=False,
    )
