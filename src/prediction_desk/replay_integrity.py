
from dataclasses import asdict, dataclass
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
class ReplayIntegrityResult:
    session_id: int
    token_id: str
    start_snapshot_id: int
    end_snapshot_id: int
    start_sequence: int
    end_sequence: int
    updates_selected: int
    updates_applied: int
    bid_differences: int
    ask_differences: int
    exact_match: bool
    error: str | None = None


def discover_snapshot_pairs(connection, session_id: int):
    rows = connection.execute(
        """
        SELECT id, token_id, message_sequence
        FROM order_book_snapshots
        WHERE stream_session_id = ?
          AND message_sequence IS NOT NULL
        ORDER BY token_id, message_sequence, id
        """,
        (session_id,),
    ).fetchall()

    pairs = []

    for _, group in groupby(rows, key=lambda row: row[1]):
        snapshots = list(group)

        for previous, current in zip(
            snapshots,
            snapshots[1:],
        ):
            if previous[2] < current[2]:
                pairs.append((previous[0], current[0]))

    return pairs


def count_differences(actual, expected):
    actual_levels = dict(actual)
    expected_levels = dict(expected)

    return sum(
        actual_levels.get(price, Decimal("0"))
        != expected_levels.get(price, Decimal("0"))
        for price in set(actual_levels) | set(expected_levels)
    )


def verify_snapshot_pair(connection, start_id, end_id):

    start = connection.execute(
        """
        SELECT token_id, stream_session_id, message_sequence
        FROM order_book_snapshots
        WHERE id = ?
        """,
        (start_id,),
    ).fetchone()

    end = connection.execute(
        """
        SELECT token_id, stream_session_id, message_sequence
        FROM order_book_snapshots
        WHERE id = ?
        """,
        (end_id,),
    ).fetchone()

    if start is None or end is None:
        raise ValueError("Snapshot not found")

    token_id, session_id, start_seq = start
    end_token, end_session, end_seq = end

    if token_id != end_token or session_id != end_session:
        raise ValueError("Snapshot token/session mismatch")

    if (
        session_id is None
        or start_seq is None
        or end_seq is None
        or start_seq >= end_seq
    ):
        raise ValueError("Invalid replay window")

    initial_check = reconstruct_snapshot(connection, start_id)
    expected_check = reconstruct_snapshot(connection, end_id)

    if not initial_check.matches_metadata:
        raise ValueError("Initial snapshot metadata mismatch")

    if not expected_check.matches_metadata:
        raise ValueError("Expected snapshot metadata mismatch")

    initial = initial_check.reconstructed
    expected = expected_check.reconstructed

    engine = BookReconstructor(
        timestamp_ms=initial.timestamp_ms,
        bids=initial.bids,
        asks=initial.asks,
    )

    rows = connection.execute(
        """
        SELECT
            id, source_timestamp_ms, side,
            price, size, message_sequence
        FROM market_level_updates
        WHERE stream_session_id = ?
          AND token_id = ?
          AND message_sequence > ?
          AND message_sequence < ?
        ORDER BY message_sequence, id
        """,
        (session_id, token_id, start_seq, end_seq),
    ).fetchall()

    applied = 0
    error = None

    for timestamp, group in groupby(
        rows,
        key=lambda row: row[1],
    ):
        batch_rows = list(group)

        try:
            engine.apply_batch([
                ReconstructionUpdate(
                    timestamp_ms=row[1],
                    side=row[2],
                    price=Decimal(row[3]),
                    size=Decimal(row[4]),
                )
                for row in batch_rows
            ])
            applied += len(batch_rows)

        except (ValueError, TypeError) as exc:
            error = (
                f"Timestamp {timestamp}: {exc}"
            )
            break

    final = engine.state()

    bid_diff = count_differences(
        final.bids, expected.bids
    )
    ask_diff = count_differences(
        final.asks, expected.asks
    )

    return ReplayIntegrityResult(
        session_id=session_id,
        token_id=token_id,
        start_snapshot_id=start_id,
        end_snapshot_id=end_id,
        start_sequence=start_seq,
        end_sequence=end_seq,
        updates_selected=len(rows),
        updates_applied=applied,
        bid_differences=bid_diff,
        ask_differences=ask_diff,
        exact_match=(
            error is None
            and bid_diff == 0
            and ask_diff == 0
        ),
        error=error,
    )


def audit_session(connection, session_id: int):
    pairs = discover_snapshot_pairs(
        connection, session_id
    )

    return [
        verify_snapshot_pair(connection, start_id, end_id)
        for start_id, end_id in pairs
    ]


def results_to_dicts(results):
    return [asdict(result) for result in results]
