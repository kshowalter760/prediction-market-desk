
from dataclasses import dataclass
from decimal import Decimal
from statistics import mean

from prediction_desk.replay_checkpoints import ReplayCheckpoint


@dataclass(frozen=True)
class CheckpointLiquidityObservation:
    token_id: str
    session_id: int
    timestamp_ms: int
    message_sequence: int
    best_bid: Decimal | None
    best_ask: Decimal | None
    spread: Decimal | None
    mid_price: Decimal | None
    bid_depth: Decimal
    ask_depth: Decimal
    total_depth: Decimal
    imbalance: Decimal | None


@dataclass(frozen=True)
class CheckpointLiquiditySummary:
    token_id: str
    session_id: int
    observation_count: int
    average_spread: Decimal | None
    minimum_spread: Decimal | None
    maximum_spread: Decimal | None
    average_total_depth: Decimal
    average_imbalance: Decimal | None
    first_mid_price: Decimal | None
    last_mid_price: Decimal | None
    mid_price_change: Decimal | None


def observation_from_checkpoint(
    checkpoint: ReplayCheckpoint,
) -> CheckpointLiquidityObservation:
    book = checkpoint.book

    mid_price = (
        (book.best_bid + book.best_ask) / Decimal("2")
        if book.best_bid is not None
        and book.best_ask is not None
        else None
    )

    return CheckpointLiquidityObservation(
        token_id=checkpoint.token_id,
        session_id=checkpoint.session_id,
        timestamp_ms=checkpoint.timestamp_ms,
        message_sequence=checkpoint.message_sequence,
        best_bid=book.best_bid,
        best_ask=book.best_ask,
        spread=book.spread,
        mid_price=mid_price,
        bid_depth=book.bid_depth,
        ask_depth=book.ask_depth,
        total_depth=book.bid_depth + book.ask_depth,
        imbalance=book.imbalance,
    )


def summarize_checkpoints(
    observations: list[CheckpointLiquidityObservation],
) -> CheckpointLiquiditySummary:
    if not observations:
        raise ValueError("No liquidity observations")

    token_id = observations[0].token_id
    session_id = observations[0].session_id

    if any(
        obs.token_id != token_id
        or obs.session_id != session_id
        for obs in observations
    ):
        raise ValueError(
            "Mixed token or session observations"
        )

    ordered = sorted(
        observations,
        key=lambda obs: (
            obs.timestamp_ms,
            obs.message_sequence,
        ),
    )

    spreads = [
        obs.spread
        for obs in ordered
        if obs.spread is not None
    ]

    imbalances = [
        obs.imbalance
        for obs in ordered
        if obs.imbalance is not None
    ]

    mid_prices = [
        obs.mid_price
        for obs in ordered
        if obs.mid_price is not None
    ]

    first_mid = mid_prices[0] if mid_prices else None
    last_mid = mid_prices[-1] if mid_prices else None

    mid_change = (
        last_mid - first_mid
        if first_mid is not None
        and last_mid is not None
        else None
    )

    return CheckpointLiquiditySummary(
        token_id=token_id,
        session_id=session_id,
        observation_count=len(ordered),
        average_spread=mean(spreads) if spreads else None,
        minimum_spread=min(spreads) if spreads else None,
        maximum_spread=max(spreads) if spreads else None,
        average_total_depth=mean(
            obs.total_depth for obs in ordered
        ),
        average_imbalance=(
            mean(imbalances) if imbalances else None
        ),
        first_mid_price=first_mid,
        last_mid_price=last_mid,
        mid_price_change=mid_change,
    )
