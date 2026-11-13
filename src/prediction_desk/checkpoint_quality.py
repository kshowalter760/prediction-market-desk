
from dataclasses import dataclass

from prediction_desk.checkpoint_research import (
    CheckpointResearchRow,
)


@dataclass(frozen=True)
class CheckpointQualityReport:
    session_id: int
    row_count: int
    token_count: int
    unique_timestamps: int
    aligned_count: int
    stale_count: int
    missing_count: int
    minimum_interval_ms: int | None
    maximum_interval_ms: int | None
    maximum_spot_age_ms: int | None
    long_gap_count: int
    independent_replay_verified: bool
    research_ready: bool
    warnings: tuple[str, ...]


def audit_checkpoint_quality(
    rows: list[CheckpointResearchRow],
    *,
    expected_interval_ms: int = 30000,
    gap_multiplier: int = 2,
    independent_replay_verified: bool = False,
) -> CheckpointQualityReport:

    if type(expected_interval_ms) is not int or expected_interval_ms <= 0:
        raise ValueError("Invalid expected interval")

    if type(gap_multiplier) is not int or gap_multiplier < 1:
        raise ValueError("Invalid gap multiplier")

    if not rows:
        raise ValueError("Cannot audit an empty dataset")

    sessions = {row.session_id for row in rows}

    if len(sessions) != 1:
        raise ValueError("Quality audit requires one session")

    timestamps = sorted({
        row.timestamp_ms for row in rows
    })

    intervals = [
        current - previous
        for previous, current in zip(
            timestamps,
            timestamps[1:],
        )
    ]

    threshold = expected_interval_ms * gap_multiplier

    long_gap_count = sum(
        interval > threshold
        for interval in intervals
    )

    aligned = sum(
        row.alignment_status == "aligned"
        for row in rows
    )

    stale = sum(
        row.alignment_status == "stale_spot"
        for row in rows
    )

    missing = sum(
        row.alignment_status == "missing_spot"
        for row in rows
    )

    spot_ages = [
        row.spot_age_ms
        for row in rows
        if row.alignment_status == "aligned"
        and row.spot_age_ms is not None
    ]

    warnings = []

    if aligned != len(rows):
        warnings.append("Not all observations are aligned")

    if len(timestamps) < 5:
        warnings.append("Very limited timestamp coverage")

    if long_gap_count:
        warnings.append("Long checkpoint gaps detected")

    if not independent_replay_verified:
        warnings.append(
            "Independent replay verification not established"
        )

    if len(timestamps) != len(rows):
        warnings.append(
            "Multiple outcome rows share timestamps; "
            "not independent market observations"
        )

    # This is a conservative eligibility gate, not a
    # certification of statistical or trading validity.
    research_ready = (
        aligned == len(rows)
        and len(timestamps) >= 5
        and long_gap_count == 0
        and independent_replay_verified
    )

    return CheckpointQualityReport(
        session_id=next(iter(sessions)),
        row_count=len(rows),
        token_count=len({row.token_id for row in rows}),
        unique_timestamps=len(timestamps),
        aligned_count=aligned,
        stale_count=stale,
        missing_count=missing,
        minimum_interval_ms=(
            min(intervals) if intervals else None
        ),
        maximum_interval_ms=(
            max(intervals) if intervals else None
        ),
        maximum_spot_age_ms=(
            max(spot_ages) if spot_ages else None
        ),
        long_gap_count=long_gap_count,
        independent_replay_verified=independent_replay_verified,
        research_ready=research_ready,
        warnings=tuple(warnings),
    )
