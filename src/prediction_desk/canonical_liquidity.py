
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RawLiquidityUpdate:
    row_id: int
    market_id: str
    token_id: str
    outcome_name: str
    timestamp_ms: int
    side: str
    price: Decimal
    size: Decimal


@dataclass(frozen=True)
class CanonicalLiquidityEvent:
    market_id: str
    timestamp_ms: int
    first_row_id: int
    second_row_id: int
    first_token_id: str
    second_token_id: str
    first_outcome: str
    second_outcome: str
    first_side: str
    second_side: str
    first_price: Decimal
    second_price: Decimal
    size: Decimal


@dataclass(frozen=True)
class PairingResult:
    events: list[CanonicalLiquidityEvent]
    unmatched_ids: list[int]
    ambiguous_ids: list[int]


def are_complementary(first, second):
    return (
        first.market_id == second.market_id
        and first.token_id != second.token_id
        and first.outcome_name != second.outcome_name
        and first.timestamp_ms == second.timestamp_ms
        and first.side != second.side
        and first.price + second.price == Decimal("1")
        and first.size == second.size
    )


def pair_liquidity_updates(updates):
    updates = list(updates)

    ids = [update.row_id for update in updates]

    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source row IDs")

    groups = defaultdict(list)

    for update in updates:
        if not isinstance(update, RawLiquidityUpdate):
            raise TypeError("Expected RawLiquidityUpdate")

        groups[
            (update.market_id, update.timestamp_ms)
        ].append(update)

    events = []
    unmatched_ids = []
    ambiguous_ids = []

    for group_key in sorted(groups):
        group = sorted(
            groups[group_key],
            key=lambda item: item.row_id,
        )

        candidates = defaultdict(list)

        for index, first in enumerate(group):
            for second in group[index + 1:]:
                if are_complementary(first, second):
                    candidates[first.row_id].append(second)
                    candidates[second.row_id].append(first)

        ambiguous = {
            row_id
            for row_id, matches in candidates.items()
            if len(matches) > 1
        }

        # Conservatively exclude all connected candidates
        # when any row has multiple possible partners.
        changed = True

        while changed:
            expanded = set(ambiguous)

            for row_id in ambiguous:
                expanded.update(
                    match.row_id
                    for match in candidates[row_id]
                )

            changed = expanded != ambiguous
            ambiguous = expanded

        ambiguous_ids.extend(sorted(ambiguous))

        paired = set()

        for first in group:
            if first.row_id in ambiguous:
                continue

            if first.row_id in paired:
                continue

            matches = candidates[first.row_id]

            if len(matches) != 1:
                unmatched_ids.append(first.row_id)
                continue

            second = matches[0]

            if second.row_id in ambiguous:
                unmatched_ids.append(first.row_id)
                continue

            paired.add(first.row_id)
            paired.add(second.row_id)

            events.append(
                CanonicalLiquidityEvent(
                    market_id=first.market_id,
                    timestamp_ms=first.timestamp_ms,
                    first_row_id=first.row_id,
                    second_row_id=second.row_id,
                    first_token_id=first.token_id,
                    second_token_id=second.token_id,
                    first_outcome=first.outcome_name,
                    second_outcome=second.outcome_name,
                    first_side=first.side,
                    second_side=second.side,
                    first_price=first.price,
                    second_price=second.price,
                    size=first.size,
                )
            )

    return PairingResult(
        events=events,
        unmatched_ids=sorted(unmatched_ids),
        ambiguous_ids=sorted(ambiguous_ids),
    )
