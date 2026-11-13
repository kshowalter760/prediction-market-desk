
import pytest

from prediction_desk.quality import (
    assess_observation_quality,
)


def test_fresh_observation():
    result = assess_observation_quality(
        source_timestamp_ms=100000,
        observed_at_utc="1970-01-01T00:01:40.500Z",
    )

    assert result.lag_ms == 500
    assert result.status == "fresh"
    assert result.usable is True


def test_stale_observation():
    result = assess_observation_quality(
        source_timestamp_ms=100000,
        observed_at_utc="1970-01-01T00:02:00Z",
    )

    assert result.status == "stale"
    assert result.usable is False


def test_future_timestamp():
    result = assess_observation_quality(
        source_timestamp_ms=105000,
        observed_at_utc="1970-01-01T00:01:40Z",
    )

    assert result.status == "future_timestamp"
    assert result.usable is False


def test_small_clock_skew_allowed():
    result = assess_observation_quality(
        source_timestamp_ms=101000,
        observed_at_utc="1970-01-01T00:01:40Z",
    )

    assert result.status == "fresh"
    assert result.lag_ms == -1000


def test_rejects_naive_datetime():
    with pytest.raises(ValueError):
        assess_observation_quality(
            100000,
            "1970-01-01T00:01:40",
        )


def test_rejects_invalid_timestamp():
    with pytest.raises(ValueError):
        assess_observation_quality(
            -1,
            "1970-01-01T00:01:40Z",
        )


def test_rejects_invalid_lag_setting():
    with pytest.raises(ValueError):
        assess_observation_quality(
            100000,
            "1970-01-01T00:01:40Z",
            max_lag_seconds=-1,
        )
