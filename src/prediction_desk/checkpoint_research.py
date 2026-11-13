
from dataclasses import dataclass
from decimal import Decimal

from prediction_desk.cross_market_alignment import (
    AlignedObservation,
)


@dataclass(frozen=True)
class CheckpointResearchRow:
    token_id: str
    session_id: int
    timestamp_ms: int
    message_sequence: int
    alignment_status: str
    spot_price_usd: Decimal | None
    spot_age_ms: int | None
    spot_return_pct: Decimal | None
    polymarket_mid_price: Decimal | None
    polymarket_mid_change: Decimal | None
    polymarket_spread: Decimal | None
    polymarket_imbalance: Decimal | None


def build_checkpoint_research(
    observations: list[AlignedObservation],
) -> list[CheckpointResearchRow]:

    if not observations:
        return []

    ordered = sorted(
        observations,
        key=lambda item: (
            item.checkpoint_timestamp_ms,
            item.token_id,
            item.message_sequence,
        ),
    )

    sessions = {item.session_id for item in ordered}

    if len(sessions) != 1:
        raise ValueError(
            "Research dataset must contain one session"
        )

    spot_by_time = {}

    for item in ordered:
        if item.alignment_status != "aligned":
            continue

        price = item.spot_price_usd

        if (
            price is None
            or not isinstance(price, Decimal)
            or not price.is_finite()
            or price <= 0
        ):
            raise ValueError("Invalid aligned spot price")

        timestamp = item.checkpoint_timestamp_ms

        previous = spot_by_time.get(timestamp)

        if previous is not None and previous != price:
            raise ValueError(
                "Conflicting spot prices at same timestamp"
            )

        spot_by_time[timestamp] = price

    spot_returns = {}
    previous_spot = None

    for timestamp in sorted(spot_by_time):
        current_spot = spot_by_time[timestamp]

        spot_returns[timestamp] = (
            (
                current_spot / previous_spot
                - Decimal("1")
            ) * Decimal("100")
            if previous_spot is not None
            else None
        )

        previous_spot = current_spot

    previous_mid_by_token = {}
    seen = set()
    rows = []

    for item in ordered:
        key = (
            item.token_id,
            item.checkpoint_timestamp_ms,
            item.message_sequence,
        )

        if key in seen:
            raise ValueError("Duplicate checkpoint")

        seen.add(key)

        current_mid = item.polymarket_mid_price
        previous_mid = previous_mid_by_token.get(
            item.token_id
        )

        mid_change = (
            current_mid - previous_mid
            if current_mid is not None
            and previous_mid is not None
            else None
        )

        if current_mid is not None:
            previous_mid_by_token[item.token_id] = current_mid

        aligned = item.alignment_status == "aligned"

        rows.append(
            CheckpointResearchRow(
                token_id=item.token_id,
                session_id=item.session_id,
                timestamp_ms=item.checkpoint_timestamp_ms,
                message_sequence=item.message_sequence,
                alignment_status=item.alignment_status,
                spot_price_usd=(
                    item.spot_price_usd if aligned else None
                ),
                spot_age_ms=(
                    item.spot_age_ms if aligned else None
                ),
                spot_return_pct=(
                    spot_returns.get(
                        item.checkpoint_timestamp_ms
                    )
                    if aligned else None
                ),
                polymarket_mid_price=current_mid,
                polymarket_mid_change=mid_change,
                polymarket_spread=item.polymarket_spread,
                polymarket_imbalance=item.polymarket_imbalance,
            )
        )

    return rows
