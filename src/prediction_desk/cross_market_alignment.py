
from dataclasses import dataclass
from decimal import Decimal
import sqlite3

from prediction_desk.replay_checkpoints import ReplayCheckpoint


@dataclass(frozen=True)
class SpotTrade:
    trade_id: int
    timestamp_ms: int
    price_usd: Decimal
    size: Decimal


@dataclass(frozen=True)
class AlignedObservation:
    token_id: str
    session_id: int
    checkpoint_timestamp_ms: int
    message_sequence: int
    polymarket_mid_price: Decimal | None
    polymarket_spread: Decimal | None
    polymarket_imbalance: Decimal | None
    spot_trade_id: int | None
    spot_timestamp_ms: int | None
    spot_price_usd: Decimal | None
    spot_age_ms: int | None
    alignment_status: str


def find_latest_spot_trade(
    connection: sqlite3.Connection,
    *,
    asset: str,
    timestamp_ms: int,
) -> SpotTrade | None:
    if not asset:
        raise ValueError("Asset must not be empty")

    if type(timestamp_ms) is not int or timestamp_ms <= 0:
        raise ValueError("Invalid timestamp")

    row = connection.execute(
        """
        SELECT
            trade_id,
            trade_timestamp_ms,
            price_usd,
            size
        FROM spot_trades
        WHERE asset = ?
          AND trade_timestamp_ms <= ?
        ORDER BY trade_timestamp_ms DESC, trade_id DESC
        LIMIT 1
        """,
        (asset, timestamp_ms),
    ).fetchone()

    if row is None:
        return None

    return SpotTrade(
        trade_id=row[0],
        timestamp_ms=row[1],
        price_usd=Decimal(row[2]),
        size=Decimal(row[3]),
    )


def align_checkpoint(
    connection: sqlite3.Connection,
    checkpoint: ReplayCheckpoint,
    *,
    asset: str = "BTC",
    max_spot_age_ms: int = 5_000,
) -> AlignedObservation:
    if (
        type(max_spot_age_ms) is not int
        or max_spot_age_ms < 0
    ):
        raise ValueError("Invalid maximum spot age")

    book = checkpoint.book

    mid_price = (
        (book.best_bid + book.best_ask) / Decimal("2")
        if book.best_bid is not None
        and book.best_ask is not None
        else None
    )

    spot = find_latest_spot_trade(
        connection,
        asset=asset,
        timestamp_ms=checkpoint.timestamp_ms,
    )

    if spot is None:
        return AlignedObservation(
            token_id=checkpoint.token_id,
            session_id=checkpoint.session_id,
            checkpoint_timestamp_ms=checkpoint.timestamp_ms,
            message_sequence=checkpoint.message_sequence,
            polymarket_mid_price=mid_price,
            polymarket_spread=book.spread,
            polymarket_imbalance=book.imbalance,
            spot_trade_id=None,
            spot_timestamp_ms=None,
            spot_price_usd=None,
            spot_age_ms=None,
            alignment_status="missing_spot",
        )

    age_ms = checkpoint.timestamp_ms - spot.timestamp_ms

    status = (
        "aligned"
        if age_ms <= max_spot_age_ms
        else "stale_spot"
    )

    return AlignedObservation(
        token_id=checkpoint.token_id,
        session_id=checkpoint.session_id,
        checkpoint_timestamp_ms=checkpoint.timestamp_ms,
        message_sequence=checkpoint.message_sequence,
        polymarket_mid_price=mid_price,
        polymarket_spread=book.spread,
        polymarket_imbalance=book.imbalance,
        spot_trade_id=spot.trade_id,
        spot_timestamp_ms=spot.timestamp_ms,
        spot_price_usd=spot.price_usd,
        spot_age_ms=age_ms,
        alignment_status=status,
    )


def align_checkpoints(
    connection: sqlite3.Connection,
    checkpoints: list[ReplayCheckpoint],
    *,
    asset: str = "BTC",
    max_spot_age_ms: int = 5_000,
) -> list[AlignedObservation]:
    return [
        align_checkpoint(
            connection,
            checkpoint,
            asset=asset,
            max_spot_age_ms=max_spot_age_ms,
        )
        for checkpoint in checkpoints
    ]
