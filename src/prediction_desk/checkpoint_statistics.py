
from dataclasses import dataclass
from decimal import Decimal

from prediction_desk.checkpoint_research import (
    CheckpointResearchRow,
)


@dataclass(frozen=True)
class CheckpointStatistics:
    token_id: str
    checkpoint_count: int
    aligned_count: int
    spot_return_count: int
    midpoint_change_count: int
    midpoint_change_events: int
    average_absolute_spot_return_pct: Decimal | None
    maximum_absolute_spot_return_pct: Decimal | None
    average_absolute_midpoint_change: Decimal | None
    correlation: float | None
    correlation_status: str


def pearson_correlation(
    x: list[Decimal],
    y: list[Decimal],
    *,
    minimum_samples: int = 5,
) -> tuple[float | None, str]:

    if len(x) != len(y):
        raise ValueError("Series lengths must match")

    if len(x) < minimum_samples:
        return None, "insufficient_samples"

    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)

    deviations_x = [value - mean_x for value in x]
    deviations_y = [value - mean_y for value in y]

    variance_x = sum(value ** 2 for value in deviations_x)
    variance_y = sum(value ** 2 for value in deviations_y)

    if variance_x == 0 or variance_y == 0:
        return None, "zero_variance"

    covariance = sum(
        a * b
        for a, b in zip(deviations_x, deviations_y)
    )

    denominator = (variance_x * variance_y).sqrt()

    return float(covariance / denominator), "calculated"


def summarize_token(
    rows: list[CheckpointResearchRow],
) -> CheckpointStatistics:

    if not rows:
        raise ValueError("At least one row is required")

    token_ids = {row.token_id for row in rows}

    if len(token_ids) != 1:
        raise ValueError("Statistics require one token")

    sessions = {row.session_id for row in rows}

    if len(sessions) != 1:
        raise ValueError("Statistics require one session")

    ordered = sorted(
        rows,
        key=lambda row: (
            row.timestamp_ms,
            row.message_sequence,
        ),
    )

    aligned = [
        row for row in ordered
        if row.alignment_status == "aligned"
    ]

    spot_returns = [
        abs(row.spot_return_pct)
        for row in aligned
        if row.spot_return_pct is not None
    ]

    mid_changes = [
        abs(row.polymarket_mid_change)
        for row in ordered
        if row.polymarket_mid_change is not None
    ]

    paired = [
        row for row in aligned
        if row.spot_return_pct is not None
        and row.polymarket_mid_change is not None
    ]

    correlation, status = pearson_correlation(
        [row.spot_return_pct for row in paired],
        [row.polymarket_mid_change for row in paired],
    )

    def average(values):
        return (
            sum(values) / len(values)
            if values
            else None
        )

    return CheckpointStatistics(
        token_id=ordered[0].token_id,
        checkpoint_count=len(ordered),
        aligned_count=len(aligned),
        spot_return_count=len(spot_returns),
        midpoint_change_count=len(mid_changes),
        midpoint_change_events=sum(
            change != 0 for change in mid_changes
        ),
        average_absolute_spot_return_pct=average(
            spot_returns
        ),
        maximum_absolute_spot_return_pct=(
            max(spot_returns) if spot_returns else None
        ),
        average_absolute_midpoint_change=average(
            mid_changes
        ),
        correlation=correlation,
        correlation_status=status,
    )
