
from dataclasses import dataclass
from decimal import Decimal
from itertools import groupby

from prediction_desk.book_reconstruction import (
    BookReconstructor,
    ReconstructionUpdate,
    ReconstructedBook,
)
from prediction_desk.snapshot_reconstruction import (
    reconstruct_snapshot,
)


@dataclass(frozen=True)
class ReplayCheckpoint:
    token_id: str
    session_id: int
    message_sequence: int
    timestamp_ms: int
    updates_applied: int
    book: ReconstructedBook


def reconstruct_checkpoints(
    connection,
    snapshot_id: int,
    *,
    interval_ms: int = 30_000,
) -> list[ReplayCheckpoint]:

    if type(snapshot_id) is not int or snapshot_id <= 0:
        raise ValueError("Invalid snapshot ID")

    if type(interval_ms) is not int or interval_ms <= 0:
        raise ValueError("interval_ms must be positive")

    metadata = connection.execute(
        """
        SELECT
            token_id,
            stream_session_id,
            message_sequence
        FROM order_book_snapshots
        WHERE id = ?
        """,
        (snapshot_id,),
    ).fetchone()

    if metadata is None:
        raise ValueError("Snapshot not found")

    token_id, session_id, start_sequence = metadata

    if session_id is None or start_sequence is None:
        raise ValueError(
            "Snapshot lacks session/sequence metadata"
        )

    verification = reconstruct_snapshot(
        connection,
        snapshot_id,
    )

    if not verification.matches_metadata:
        raise ValueError(
            "Snapshot metadata mismatch"
        )

    initial = verification.reconstructed

    engine = BookReconstructor(
        timestamp_ms=initial.timestamp_ms,
        bids=initial.bids,
        asks=initial.asks,
    )

    rows = connection.execute(
        """
        SELECT
            id,
            source_timestamp_ms,
            side,
            price,
            size,
            message_sequence
        FROM market_level_updates
        WHERE token_id = ?
          AND stream_session_id = ?
          AND message_sequence > ?
        ORDER BY message_sequence, id
        """,
        (token_id, session_id, start_sequence),
    ).fetchall()

    checkpoints = []
    applied = 0
    last_checkpoint_ms = initial.timestamp_ms

    # Preserve recorded message ordering.
    # Consecutive updates sharing a source timestamp
    # are applied atomically as a reconstruction assumption.
    for timestamp_ms, group in groupby(
        rows,
        key=lambda row: row[1],
    ):
        batch = list(group)

        updates = [
            ReconstructionUpdate(
                timestamp_ms=row[1],
                side=row[2],
                price=Decimal(row[3]),
                size=Decimal(row[4]),
            )
            for row in batch
        ]

        engine.apply_batch(updates)
        applied += len(updates)

        if timestamp_ms - last_checkpoint_ms >= interval_ms:
            checkpoints.append(
                ReplayCheckpoint(
                    token_id=token_id,
                    session_id=session_id,
                    message_sequence=batch[-1][5],
                    timestamp_ms=timestamp_ms,
                    updates_applied=applied,
                    book=engine.state(),
                )
            )

            last_checkpoint_ms = timestamp_ms

    return checkpoints
