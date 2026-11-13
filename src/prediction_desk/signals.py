from prediction_desk.quality import assess_observation_quality
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class PriceShock:
    token_id: str
    market_id: str
    outcome_name: str
    previous_timestamp_ms: int
    current_timestamp_ms: int
    previous_midpoint: Decimal
    current_midpoint: Decimal
    change: Decimal


def midpoint_from_row(row, max_spread):
    try:
        bid = Decimal(str(row["best_bid"]))
        ask = Decimal(str(row["best_ask"]))
    except (KeyError, TypeError, InvalidOperation):
        return None

    if not bid.is_finite() or not ask.is_finite():
        return None

    if not (Decimal("0") < bid < ask < Decimal("1")):
        return None

    if ask - bid > max_spread:
        return None

    return (bid + ask) / Decimal("2")


def detect_price_shocks(
    history,
    threshold=Decimal("0.10"),
    max_spread=Decimal("0.03"),
    max_gap_seconds=60,
    require_fresh=False,
):
    if not isinstance(threshold, Decimal):
        raise TypeError("threshold must be Decimal")

    if not isinstance(max_spread, Decimal):
        raise TypeError("max_spread must be Decimal")

    if not threshold.is_finite() or not 0 < threshold < 1:
        raise ValueError("threshold must be between 0 and 1")

    if not max_spread.is_finite() or not 0 < max_spread < 1:
        raise ValueError("max_spread must be between 0 and 1")

    if (
        not isinstance(max_gap_seconds, int)
        or isinstance(max_gap_seconds, bool)
        or max_gap_seconds <= 0
    ):
        raise ValueError(
            "max_gap_seconds must be a positive integer"
        )
    if not isinstance(require_fresh, bool):
        raise TypeError("require_fresh must be a boolean")

    ordered = sorted(
        history,
        key=lambda row: row["source_timestamp_ms"],
    )

    shocks = []
    previous = None

    for row in ordered:
        midpoint = midpoint_from_row(row, max_spread)

        if midpoint is None:
            previous = None
            continue

        if require_fresh:
            try:
                quality = assess_observation_quality(
                    source_timestamp_ms=row[
                        "source_timestamp_ms"
                    ],
                    observed_at_utc=row[
                        "observed_at_utc"
                    ],
                )
            except (KeyError, TypeError, ValueError):
                previous = None
                continue

            if not quality.usable:
                previous = None
                continue

        if previous is not None:
            previous_row, previous_midpoint = previous
            elapsed_ms = (
                row["source_timestamp_ms"]
                - previous_row["source_timestamp_ms"]
            )

            if elapsed_ms > max_gap_seconds * 1000:
                previous = (row, midpoint)
                continue

            if (
                row["token_id"] == previous_row["token_id"]
                and row["source_timestamp_ms"]
                > previous_row["source_timestamp_ms"]
            ):
                change = midpoint - previous_midpoint

                if abs(change) >= threshold:
                    shocks.append(
                        PriceShock(
                            token_id=row["token_id"],
                            market_id=row["market_id"],
                            outcome_name=row["outcome_name"],
                            previous_timestamp_ms=(
                                previous_row["source_timestamp_ms"]
                            ),
                            current_timestamp_ms=(
                                row["source_timestamp_ms"]
                            ),
                            previous_midpoint=previous_midpoint,
                            current_midpoint=midpoint,
                            change=change,
                        )
                    )

        previous = (row, midpoint)

    return shocks
