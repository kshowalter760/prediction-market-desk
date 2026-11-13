from itertools import groupby
import argparse
import sqlite3
from decimal import Decimal
from pathlib import Path

from prediction_desk.book_reconstruction import (
    BookReconstructor,
    ReconstructionUpdate,
)
from prediction_desk.snapshot_reconstruction import (
    reconstruct_snapshot,
)


DATABASE = Path("data/prediction_markets.db")

DEFAULT_PAIRS = (
    (63, 65),
    (64, 66),
    (65, 67),
    (66, 68),
)


def load_snapshot_metadata(connection, snapshot_id):
    row = connection.execute(
        """
        SELECT
            id,
            token_id,
            stream_session_id,
            message_sequence,
            source_timestamp_ms
        FROM order_book_snapshots
        WHERE id = ?
        """,
        (snapshot_id,),
    ).fetchone()

    if row is None:
        raise ValueError(
            f"Snapshot {snapshot_id} does not exist"
        )

    return row


def compare_levels(actual, expected):
    actual_levels = dict(actual)
    expected_levels = dict(expected)

    differences = []

    for price in sorted(
        set(actual_levels) | set(expected_levels)
    ):
        actual_size = actual_levels.get(
            price, Decimal("0")
        )
        expected_size = expected_levels.get(
            price, Decimal("0")
        )

        if actual_size != expected_size:
            differences.append(
                (price, actual_size, expected_size)
            )

    return differences


def compare_snapshots(
    connection,
    start_snapshot_id,
    end_snapshot_id,
):
    start = load_snapshot_metadata(
        connection, start_snapshot_id
    )
    end = load_snapshot_metadata(
        connection, end_snapshot_id
    )

    if start["token_id"] != end["token_id"]:
        raise ValueError(
            "Snapshots belong to different tokens"
        )

    if (
        start["stream_session_id"] is None
        or start["stream_session_id"]
        != end["stream_session_id"]
    ):
        raise ValueError(
            "Snapshots must belong to the same stream session"
        )

    start_sequence = start["message_sequence"]
    end_sequence = end["message_sequence"]

    if (
        start_sequence is None
        or end_sequence is None
        or start_sequence >= end_sequence
    ):
        raise ValueError(
            "Invalid snapshot message sequence range"
        )

    initial_verification = reconstruct_snapshot(
        connection, start_snapshot_id
    )
    expected_verification = reconstruct_snapshot(
        connection, end_snapshot_id
    )

    if not initial_verification.matches_metadata:
        raise ValueError(
            "Starting snapshot metadata mismatch"
        )

    if not expected_verification.matches_metadata:
        raise ValueError(
            "Ending snapshot metadata mismatch"
        )

    initial = initial_verification.reconstructed
    expected = expected_verification.reconstructed

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
        WHERE stream_session_id = ?
          AND token_id = ?
          AND message_sequence > ?
          AND message_sequence < ?
        ORDER BY
            message_sequence ASC,
            id ASC
        """,
        (
            start["stream_session_id"],
            start["token_id"],
            start_sequence,
            end_sequence,
        ),
    ).fetchall()


    applied = 0
    replay_error = None

    # Rows are already ordered by message_sequence, id.
    # Group consecutive updates with the same source timestamp.
    # This is a reconstruction assumption, not a verified
    # exchange-level atomic message boundary.
    for timestamp_ms, grouped_rows in groupby(
        rows,
        key=lambda row: row["source_timestamp_ms"],
    ):
        batch_rows = list(grouped_rows)

        updates = [
            ReconstructionUpdate(
                timestamp_ms=row["source_timestamp_ms"],
                side=row["side"],
                price=Decimal(row["price"]),
                size=Decimal(row["size"]),
            )
            for row in batch_rows
        ]

        try:
            engine.apply_batch(updates)
            applied += len(updates)

        except (ValueError, TypeError) as exc:
            replay_error = (
                f"Timestamp {timestamp_ms}, "
                f"sequences "
                f"{batch_rows[0]['message_sequence']}–"
                f"{batch_rows[-1]['message_sequence']}: "
                f"{exc}"
            )
            break


    reconstructed = engine.state()

    bid_differences = compare_levels(
        reconstructed.bids, expected.bids
    )
    ask_differences = compare_levels(
        reconstructed.asks, expected.asks
    )

    matches = (
        replay_error is None
        and not bid_differences
        and not ask_differences
    )

    print()
    print("=" * 70)
    print(
        f"SNAPSHOT COMPARISON "
        f"{start_snapshot_id} -> {end_snapshot_id}"
    )
    print("=" * 70)

    print("Token:", start["token_id"][:20] + "...")
    print("Session:", start["stream_session_id"])
    print(
        "Sequence range:",
        start_sequence,
        "->",
        end_sequence,
    )
    print("Updates selected:", len(rows))
    print("Updates applied:", applied)

    print()
    print("RECONSTRUCTED VS OBSERVED")
    print(
        "Bid levels:",
        len(reconstructed.bids),
        "/",
        len(expected.bids),
    )
    print(
        "Ask levels:",
        len(reconstructed.asks),
        "/",
        len(expected.asks),
    )
    print(
        "Best bid:",
        reconstructed.best_bid,
        "/",
        expected.best_bid,
    )
    print(
        "Best ask:",
        reconstructed.best_ask,
        "/",
        expected.best_ask,
    )

    print()
    print("Bid differences:", len(bid_differences))
    print("Ask differences:", len(ask_differences))

    if replay_error is not None:
        print("Replay error:", replay_error)

    for side, differences in (
        ("BUY", bid_differences),
        ("SELL", ask_differences),
    ):
        for price, actual, observed in differences[:10]:
            print(
                f"{side} price={price} "
                f"reconstructed={actual} "
                f"observed={observed}"
            )

        if len(differences) > 10:
            print(
                f"{side}: "
                f"{len(differences) - 10} "
                "additional differences omitted"
            )

    if matches:
        print("\nRESULT: EXACT DEPTH MATCH")
    else:
        print("\nRESULT: DEPTH MISMATCH")

    return matches


def main():
    parser = argparse.ArgumentParser(
        description="Compare reconstructed and observed order books"
    )
    parser.add_argument(
        "--start",
        type=int,
        help="Starting snapshot ID",
    )
    parser.add_argument(
        "--end",
        type=int,
        help="Ending snapshot ID",
    )

    args = parser.parse_args()

    if (args.start is None) != (args.end is None):
        parser.error(
            "--start and --end must be supplied together"
        )

    if not DATABASE.is_file():
        raise FileNotFoundError(DATABASE)

    pairs = (
        ((args.start, args.end),)
        if args.start is not None
        else DEFAULT_PAIRS
    )

    connection = sqlite3.connect(
        f"file:{DATABASE.resolve().as_posix()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row

    try:
        results = []

        for start_id, end_id in pairs:
            results.append(
                compare_snapshots(
                    connection,
                    start_id,
                    end_id,
                )
            )

        print()
        print("=" * 70)
        print("FINAL COMPARISON SUMMARY")
        print("=" * 70)
        print("Windows tested:", len(results))
        print("Exact matches:", sum(results))
        print("Mismatches:", len(results) - sum(results))

    finally:
        connection.close()


if __name__ == "__main__":
    main()
