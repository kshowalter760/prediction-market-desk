
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


@dataclass(frozen=True)
class LevelUpdate:
    token_id: str
    timestamp_ms: int
    side: str
    price: Decimal
    size: Decimal


@dataclass(frozen=True)
class LiquidityMovement:
    token_id: str
    timestamp_ms: int
    side: str
    price: Decimal
    previous_size: Decimal | None
    current_size: Decimal
    size_change: Decimal | None
    classification: str


class LiquidityTracker:
    """
    Reconstructs observed price-level size changes.

    State is maintained independently for each:
        (token_id, side, price)

    Initial observations establish baselines rather
    than being counted as liquidity additions.
    """

    def __init__(self):
        self.level_sizes = {}
        self.last_timestamps = {}
        self.last_global_timestamp = None

    def process(self, update: LevelUpdate):
        self._validate(update)

        if (
            self.last_global_timestamp is not None
            and update.timestamp_ms < self.last_global_timestamp
        ):
            raise ValueError(
                "Updates must be processed in timestamp order"
            )

        key = (
            update.token_id,
            update.side,
            update.price,
        )

        previous_timestamp = self.last_timestamps.get(key)
        previous_size = self.level_sizes.get(key)

        if previous_timestamp == update.timestamp_ms:
            if previous_size == update.size:
                return None

            raise ValueError(
                "Conflicting updates at the same timestamp"
            )

        if previous_size is None:
            classification = "baseline"
            size_change = None

        else:
            size_change = update.size - previous_size

            if size_change > 0:
                classification = "addition"

            elif size_change < 0 and update.size == 0:
                classification = "removal"

            elif size_change < 0:
                classification = "reduction"

            else:
                classification = "unchanged"

        movement = LiquidityMovement(
            token_id=update.token_id,
            timestamp_ms=update.timestamp_ms,
            side=update.side,
            price=update.price,
            previous_size=previous_size,
            current_size=update.size,
            size_change=size_change,
            classification=classification,
        )

        self.level_sizes[key] = update.size
        self.last_timestamps[key] = update.timestamp_ms
        self.last_global_timestamp = update.timestamp_ms

        return movement

    @staticmethod
    def _validate(update):
        if not isinstance(update, LevelUpdate):
            raise TypeError("Expected LevelUpdate")

        if (
            not isinstance(update.token_id, str)
            or not update.token_id.isdigit()
        ):
            raise ValueError("Invalid token ID")

        if (
            type(update.timestamp_ms) is not int
            or update.timestamp_ms <= 0
        ):
            raise ValueError("Invalid timestamp")

        if update.side not in ("BUY", "SELL"):
            raise ValueError("Invalid side")

        if (
            not isinstance(update.price, Decimal)
            or not update.price.is_finite()
            or not Decimal("0") < update.price < Decimal("1")
        ):
            raise ValueError("Invalid price")

        if (
            not isinstance(update.size, Decimal)
            or not update.size.is_finite()
            or update.size < 0
        ):
            raise ValueError("Invalid size")


def analyze_liquidity(
    updates: Iterable[LevelUpdate],
) -> list[LiquidityMovement]:
    tracker = LiquidityTracker()
    movements = []

    for update in updates:
        movement = tracker.process(update)

        if movement is not None:
            movements.append(movement)

    return movements


def summarize_liquidity(movements):
    summary = {
        "baseline": 0,
        "addition": 0,
        "reduction": 0,
        "removal": 0,
        "unchanged": 0,
        "total_added": Decimal("0"),
        "total_reduced": Decimal("0"),
    }

    for movement in movements:
        summary[movement.classification] += 1

        if movement.size_change is None:
            continue

        if movement.size_change > 0:
            summary["total_added"] += movement.size_change

        elif movement.size_change < 0:
            summary["total_reduced"] += abs(
                movement.size_change
            )

    return summary
