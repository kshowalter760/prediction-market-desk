
from decimal import Decimal

import pytest

from prediction_desk.signals import detect_price_shocks


def make_row(timestamp, bid, ask):
    return {
        "token_id": "123",
        "market_id": "100",
        "outcome_name": "Up",
        "source_timestamp_ms": timestamp,
        "best_bid": bid,
        "best_ask": ask,
    }


def test_detects_large_downward_shock():
    history = [
        make_row(2000, "0.44", "0.45"),
        make_row(1000, "0.67", "0.68"),
    ]

    shocks = detect_price_shocks(history)

    assert len(shocks) == 1
    assert shocks[0].change == Decimal("-0.23")


def test_ignores_small_movement():
    history = [
        make_row(1000, "0.50", "0.51"),
        make_row(2000, "0.52", "0.53"),
    ]

    assert detect_price_shocks(history) == []


def test_rejects_wide_spread():
    history = [
        make_row(1000, "0.40", "0.50"),
        make_row(2000, "0.60", "0.61"),
    ]

    assert detect_price_shocks(history) == []


def test_rejects_missing_quote():
    history = [
        make_row(1000, None, "0.50"),
        make_row(2000, "0.60", "0.61"),
    ]

    assert detect_price_shocks(history) == []


def test_rejects_invalid_threshold():
    with pytest.raises(ValueError):
        detect_price_shocks(
            [],
            threshold=Decimal("-0.1"),
        )


def test_no_comparison_across_invalid_snapshot():
    history = [
        make_row(1000, "0.20", "0.21"),
        make_row(2000, "0.30", "0.40"),
        make_row(3000, "0.70", "0.71"),
    ]

    assert detect_price_shocks(history) == []


def test_rejects_shock_across_long_gap():
    history = [
        make_row(1000, "0.40", "0.41"),
        make_row(121000, "0.70", "0.71"),
    ]

    shocks = detect_price_shocks(
        history,
        max_gap_seconds=60,
    )

    assert shocks == []


def test_detects_shock_within_time_window():
    history = [
        make_row(1000, "0.40", "0.41"),
        make_row(21000, "0.70", "0.71"),
    ]

    shocks = detect_price_shocks(
        history,
        max_gap_seconds=60,
    )

    assert len(shocks) == 1
    assert shocks[0].change == Decimal("0.30")


def test_rejects_invalid_max_gap():
    with pytest.raises(ValueError):
        detect_price_shocks(
            [],
            max_gap_seconds=0,
        )


def test_fresh_observations_can_trigger_shock():
    history = [
        {
            **make_row(100000, "0.40", "0.41"),
            "observed_at_utc": "1970-01-01T00:01:41Z",
        },
        {
            **make_row(120000, "0.70", "0.71"),
            "observed_at_utc": "1970-01-01T00:02:01Z",
        },
    ]

    shocks = detect_price_shocks(
        history,
        require_fresh=True,
    )

    assert len(shocks) == 1
    assert shocks[0].change == Decimal("0.30")


def test_stale_observation_breaks_comparison():
    history = [
        {
            **make_row(100000, "0.20", "0.21"),
            "observed_at_utc": "1970-01-01T00:01:41Z",
        },
        {
            **make_row(120000, "0.40", "0.41"),
            "observed_at_utc": "1970-01-01T00:02:20Z",
        },
        {
            **make_row(140000, "0.70", "0.71"),
            "observed_at_utc": "1970-01-01T00:02:21Z",
        },
    ]

    shocks = detect_price_shocks(
        history,
        require_fresh=True,
    )

    assert shocks == []


def test_missing_quality_metadata_fails_closed():
    history = [
        make_row(100000, "0.40", "0.41"),
        make_row(120000, "0.70", "0.71"),
    ]

    shocks = detect_price_shocks(
        history,
        require_fresh=True,
    )

    assert shocks == []
