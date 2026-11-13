
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ObservationQuality:
    lag_ms: int
    status: str
    usable: bool


def assess_observation_quality(
    source_timestamp_ms,
    observed_at_utc,
    max_lag_seconds=10,
    future_tolerance_seconds=2,
):
    if (
        not isinstance(source_timestamp_ms, int)
        or isinstance(source_timestamp_ms, bool)
        or source_timestamp_ms <= 0
    ):
        raise ValueError("Invalid source timestamp")

    for name, value in (
        ("max_lag_seconds", max_lag_seconds),
        ("future_tolerance_seconds", future_tolerance_seconds),
    ):
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 0
        ):
            raise ValueError(f"Invalid {name}")

    if not isinstance(observed_at_utc, str):
        raise ValueError("Invalid observation timestamp")

    try:
        observed = datetime.fromisoformat(
            observed_at_utc.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ValueError(
            "Invalid observation timestamp"
        ) from exc

    if observed.tzinfo is None:
        raise ValueError(
            "Observation timestamp must be timezone-aware"
        )

    observed_ms = int(
        observed.astimezone(
            timezone.utc
        ).timestamp() * 1000
    )

    lag_ms = observed_ms - source_timestamp_ms

    if lag_ms < -(future_tolerance_seconds * 1000):
        return ObservationQuality(
            lag_ms=lag_ms,
            status="future_timestamp",
            usable=False,
        )

    if lag_ms > max_lag_seconds * 1000:
        return ObservationQuality(
            lag_ms=lag_ms,
            status="stale",
            usable=False,
        )

    return ObservationQuality(
        lag_ms=lag_ms,
        status="fresh",
        usable=True,
    )
