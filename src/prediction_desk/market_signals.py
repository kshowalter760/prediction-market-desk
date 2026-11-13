
from dataclasses import dataclass
from decimal import Decimal

from prediction_desk.signals import PriceShock


@dataclass(frozen=True)
class MarketShock:
    market_id: str
    timestamp_ms: int
    magnitude: Decimal
    outcome_shocks: tuple[PriceShock, ...]


def are_complementary(
    first: PriceShock,
    second: PriceShock,
    tolerance_ms: int,
    magnitude_tolerance: Decimal,
):
    if first.market_id != second.market_id:
        return False

    if first.token_id == second.token_id:
        return False

    if {first.outcome_name, second.outcome_name} != {
        "Up", "Down"
    }:
        return False

    if first.change * second.change >= 0:
        return False

    if (
        abs(
            first.previous_timestamp_ms
            - second.previous_timestamp_ms
        )
        > tolerance_ms
    ):
        return False

    if (
        abs(
            first.current_timestamp_ms
            - second.current_timestamp_ms
        )
        > tolerance_ms
    ):
        return False

    if (
        abs(abs(first.change) - abs(second.change))
        > magnitude_tolerance
    ):
        return False

    return True


def consolidate_market_shocks(
    shocks,
    tolerance_ms=2000,
    magnitude_tolerance=Decimal("0.03"),
):
    if (
        not isinstance(tolerance_ms, int)
        or isinstance(tolerance_ms, bool)
        or tolerance_ms < 0
    ):
        raise ValueError(
            "tolerance_ms must be nonnegative"
        )

    if not isinstance(magnitude_tolerance, Decimal):
        raise TypeError(
            "magnitude_tolerance must be Decimal"
        )

    if (
        not magnitude_tolerance.is_finite()
        or not 0 <= magnitude_tolerance < 1
    ):
        raise ValueError(
            "Invalid magnitude tolerance"
        )

    shocks = list(shocks)

    if not all(
        isinstance(shock, PriceShock)
        for shock in shocks
    ):
        raise TypeError(
            "All shocks must be PriceShock objects"
        )

    ordered = sorted(
        shocks,
        key=lambda shock: (
            shock.market_id,
            shock.current_timestamp_ms,
            shock.token_id,
        ),
    )

    groups = []
    matched_indices = set()

    for index, shock in enumerate(ordered):
        if index in matched_indices:
            continue

        group = [shock]
        matched_indices.add(index)

        for other_index in range(index + 1, len(ordered)):
            if other_index in matched_indices:
                continue

            candidate = ordered[other_index]

            if are_complementary(
                shock,
                candidate,
                tolerance_ms,
                magnitude_tolerance,
            ):
                group.append(candidate)
                matched_indices.add(other_index)
                break

        groups.append(group)

    return [
        MarketShock(
            market_id=group[0].market_id,
            timestamp_ms=min(
                shock.current_timestamp_ms
                for shock in group
            ),
            magnitude=max(
                abs(shock.change)
                for shock in group
            ),
            outcome_shocks=tuple(group),
        )
        for group in groups
    ]
