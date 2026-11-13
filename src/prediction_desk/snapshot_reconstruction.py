
from dataclasses import dataclass
from decimal import Decimal

from prediction_desk.book_reconstruction import (
    BookReconstructor,
    ReconstructedBook,
)


@dataclass(frozen=True)
class SnapshotVerification:
    snapshot_id: int
    token_id: str
    reconstructed: ReconstructedBook
    stored_best_bid: Decimal | None
    stored_best_ask: Decimal | None
    stored_spread: Decimal | None
    matches_metadata: bool


def optional_decimal(value):
    return Decimal(value) if value is not None else None


def reconstruct_snapshot(connection, snapshot_id: int):
    if type(snapshot_id) is not int or snapshot_id <= 0:
        raise ValueError("Invalid snapshot ID")

    snapshot = connection.execute(
        """
        SELECT
            token_id,
            source_timestamp_ms,
            best_bid,
            best_ask,
            spread
        FROM order_book_snapshots
        WHERE id = ?
        """,
        (snapshot_id,),
    ).fetchone()

    if snapshot is None:
        raise ValueError("Snapshot not found")

    (
        token_id,
        timestamp_ms,
        stored_bid,
        stored_ask,
        stored_spread,
    ) = snapshot

    rows = connection.execute(
        """
        SELECT side, price, size
        FROM order_book_levels
        WHERE snapshot_id = ?
        ORDER BY id
        """,
        (snapshot_id,),
    ).fetchall()

    if not rows:
        raise ValueError(
            "Snapshot has no persisted depth levels"
        )

    bids = []
    asks = []

    for side, price, size in rows:
        level = (Decimal(price), Decimal(size))

        if side == "BUY":
            bids.append(level)
        elif side == "SELL":
            asks.append(level)
        else:
            raise ValueError("Unknown book side")

    engine = BookReconstructor(
        timestamp_ms=timestamp_ms,
        bids=bids,
        asks=asks,
    )

    reconstructed = engine.state()

    stored_bid = optional_decimal(stored_bid)
    stored_ask = optional_decimal(stored_ask)
    stored_spread = optional_decimal(stored_spread)

    matches_metadata = (
        reconstructed.best_bid == stored_bid
        and reconstructed.best_ask == stored_ask
        and reconstructed.spread == stored_spread
    )

    return SnapshotVerification(
        snapshot_id=snapshot_id,
        token_id=token_id,
        reconstructed=reconstructed,
        stored_best_bid=stored_bid,
        stored_best_ask=stored_ask,
        stored_spread=stored_spread,
        matches_metadata=matches_metadata,
    )
