
from dataclasses import dataclass
from decimal import Decimal

from prediction_desk.canonical_liquidity import (
    CanonicalLiquidityEvent,
)
from prediction_desk.liquidity_analytics import (
    LevelUpdate,
    analyze_liquidity,
    summarize_liquidity,
)


@dataclass(frozen=True)
class NormalizedLiquidityReport:
    market_id: str
    outcome: str
    side: str
    canonical_events: int
    normalized_updates: int
    excluded_events: int
    summary: dict
    movements: list


def normalize_outcome_side(
    events: list[CanonicalLiquidityEvent],
    outcome: str = "Up",
    side: str = "BUY",
) -> NormalizedLiquidityReport:
    if not events:
        raise ValueError("No canonical events supplied")

    if outcome not in ("Up", "Down"):
        raise ValueError("Unsupported outcome")

    if side not in ("BUY", "SELL"):
        raise ValueError("Unsupported side")

    market_ids = {event.market_id for event in events}

    if len(market_ids) != 1:
        raise ValueError("Expected one market")

    market_id = next(iter(market_ids))
    selected = []
    excluded = 0

    for event in events:
        first_matches = (
            event.first_outcome == outcome
            and event.first_side == side
        )

        second_matches = (
            event.second_outcome == outcome
            and event.second_side == side
        )

        if first_matches == second_matches:
            excluded += 1
            continue

        if first_matches:
            token_id = event.first_token_id
            price = event.first_price
            row_id = event.first_row_id
        else:
            token_id = event.second_token_id
            price = event.second_price
            row_id = event.second_row_id

        selected.append(
            (
                event.timestamp_ms,
                row_id,
                LevelUpdate(
                    token_id=token_id,
                    timestamp_ms=event.timestamp_ms,
                    side=side,
                    price=price,
                    size=event.size,
                ),
            )
        )

    selected.sort(key=lambda item: (item[0], item[1]))

    updates = [item[2] for item in selected]
    movements = analyze_liquidity(updates)

    return NormalizedLiquidityReport(
        market_id=market_id,
        outcome=outcome,
        side=side,
        canonical_events=len(events),
        normalized_updates=len(updates),
        excluded_events=excluded,
        summary=summarize_liquidity(movements),
        movements=movements,
    )
