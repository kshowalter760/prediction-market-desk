
from dataclasses import dataclass
from decimal import Decimal
from itertools import groupby

from prediction_desk.book_reconstruction import (
    BookReconstructor,
    ReconstructionUpdate,
)
from prediction_desk.snapshot_reconstruction import (
    reconstruct_snapshot,
)


@dataclass(frozen=True)
class SnapshotPairVerification:
    initial_snapshot_id: int
    final_snapshot_id: int
    token_id: str
    session_id: int
    updates_applied: int
    depth_matches: bool
    metadata_matches: bool
    continuity_verified: bool
    absolute_size_semantics_verified: bool

    @property
    def independently_verified(self) -> bool:
        return (
            self.depth_matches
            and self.metadata_matches
        )


def verify_snapshot_pair(
    connection,
    initial_snapshot_id: int,
    final_snapshot_id: int,
    *,
    max_updates: int = 100_000,
) -> SnapshotPairVerification:

    for snapshot_id in (
        initial_snapshot_id,
        final_snapshot_id,
    ):
        if type(snapshot_id) is not int or snapshot_id <= 0:
            raise ValueError("Invalid snapshot ID")

    if initial_snapshot_id == final_snapshot_id:
        raise ValueError("Snapshots must be different")

    if type(max_updates) is not int or max_updates <= 0:
        raise ValueError("max_updates must be positive")

    metadata = connection.execute(
        """
        SELECT
            id,
            token_id,
            stream_session_id,
            message_sequence,
            source_timestamp_ms
        FROM order_book_snapshots
        WHERE id IN (?, ?)
        """,
        (initial_snapshot_id, final_snapshot_id),
    ).fetchall()

    if len(metadata) != 2:
        raise ValueError("Snapshot not found")

    snapshots = {row[0]: row for row in metadata}

    initial_row = snapshots[initial_snapshot_id]
    final_row = snapshots[final_snapshot_id]

    _, initial_token, initial_session, initial_seq, initial_ms = (
        initial_row
    )
    _, final_token, final_session, final_seq, final_ms = (
        final_row
    )

    if initial_token != final_token:
        raise ValueError("Snapshots belong to different tokens")

    if initial_session is None or final_session is None:
        raise ValueError("Missing session metadata")

    if initial_session != final_session:
        raise ValueError("Snapshots belong to different sessions")

    if initial_seq is None or final_seq is None:
        raise ValueError("Missing sequence metadata")

    if final_seq <= initial_seq:
        raise ValueError("Final snapshot must have a later sequence")

    if final_ms < initial_ms:
        raise ValueError("Final snapshot timestamp precedes initial")

    initial_verification = reconstruct_snapshot(
        connection,
        initial_snapshot_id,
    )

    final_verification = reconstruct_snapshot(
        connection,
        final_snapshot_id,
    )

    if not initial_verification.matches_metadata:
        raise ValueError("Initial snapshot metadata mismatch")

    if not final_verification.matches_metadata:
        raise ValueError("Final snapshot metadata mismatch")

    initial_book = initial_verification.reconstructed
    final_book = final_verification.reconstructed

    engine = BookReconstructor(
        timestamp_ms=initial_book.timestamp_ms,
        bids=initial_book.bids,
        asks=initial_book.asks,
    )

    rows = connection.execute(
        """
        SELECT
            source_timestamp_ms,
            side,
            price,
            size,
            message_sequence
        FROM market_level_updates
        WHERE token_id = ?
          AND stream_session_id = ?
          AND message_sequence > ?
          AND message_sequence <= ?
        ORDER BY message_sequence, id
        LIMIT ?
        """,
        (
            initial_token,
            initial_session,
            initial_seq,
            final_seq,
            max_updates + 1,
        ),
    ).fetchall()

    if len(rows) > max_updates:
        raise ValueError(
            "Replay exceeds max_updates; refusing partial result"
        )

    for row in rows:
        if row[0] is None:
            raise ValueError("Update missing source timestamp")

        if row[0] < initial_ms or row[0] > final_ms:
            raise ValueError(
                "Update timestamp outside snapshot interval"
            )

    # Apply consecutive timestamp batches in recorded sequence order.
    # This does not prove that the source stream was complete.
    for timestamp_ms, group in groupby(
        rows,
        key=lambda row: row[0],
    ):
        batch = list(group)

        updates = [
            ReconstructionUpdate(
                timestamp_ms=timestamp_ms,
                side=row[1],
                price=Decimal(row[2]),
                size=Decimal(row[3]),
            )
            for row in batch
        ]

        engine.apply_batch(updates)

    replayed_book = engine.state()

    depth_matches = (
        replayed_book.bids == final_book.bids
        and replayed_book.asks == final_book.asks
    )

    metadata_matches = (
        final_verification.matches_metadata
    )

    return SnapshotPairVerification(
        initial_snapshot_id=initial_snapshot_id,
        final_snapshot_id=final_snapshot_id,
        token_id=initial_token,
        session_id=initial_session,
        updates_applied=len(rows),
        depth_matches=depth_matches,
        metadata_matches=metadata_matches,
        continuity_verified=False,
        absolute_size_semantics_verified=False,
    )
