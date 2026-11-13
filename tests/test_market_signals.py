
from decimal import Decimal

import pytest

from prediction_desk.market_signals import (
    consolidate_market_shocks,
)
from prediction_desk.signals import PriceShock


def make_shock(
    token_id,
    outcome_name,
    timestamp,
    change,
    market_id="100",
):
    return PriceShock(
        token_id=token_id,
        market_id=market_id,
        outcome_name=outcome_name,
        previous_timestamp_ms=timestamp - 20000,
        current_timestamp_ms=timestamp,
        previous_midpoint=Decimal("0.50"),
        current_midpoint=(
            Decimal("0.50") + Decimal(change)
        ),
        change=Decimal(change),
    )


def test_merges_complementary_outcomes():
    shocks = [
        make_shock("123", "Up", 100000, "-0.23"),
        make_shock("456", "Down", 100230, "0.23"),
    ]

    events = consolidate_market_shocks(shocks)

    assert len(events) == 1
    assert len(events[0].outcome_shocks) == 2
    assert events[0].magnitude == Decimal("0.23")


def test_keeps_separate_markets():
    shocks = [
        make_shock("123", "Up", 100000, "-0.23"),
        make_shock(
            "789", "Up", 100200, "-0.20",
            market_id="200",
        ),
    ]

    assert len(consolidate_market_shocks(shocks)) == 2


def test_keeps_distant_events_separate():
    shocks = [
        make_shock("123", "Up", 100000, "-0.23"),
        make_shock("456", "Down", 105000, "0.23"),
    ]

    assert len(consolidate_market_shocks(shocks)) == 2


def test_does_not_merge_same_outcome():
    shocks = [
        make_shock("123", "Up", 100000, "-0.23"),
        make_shock("123", "Up", 100200, "0.20"),
    ]

    assert len(consolidate_market_shocks(shocks)) == 2


def test_rejects_invalid_tolerance():
    with pytest.raises(ValueError):
        consolidate_market_shocks(
            [],
            tolerance_ms=-1,
        )


def test_same_direction_not_merged():
    shocks = [
        make_shock("123", "Up", 100000, "0.20"),
        make_shock("456", "Down", 100200, "0.20"),
    ]

    events = consolidate_market_shocks(shocks)

    assert len(events) == 2


def test_mismatched_magnitudes_not_merged():
    shocks = [
        make_shock("123", "Up", 100000, "-0.20"),
        make_shock("456", "Down", 100200, "0.30"),
    ]

    events = consolidate_market_shocks(shocks)

    assert len(events) == 2


def test_mismatched_previous_windows_not_merged():
    first = make_shock(
        "123", "Up", 100000, "-0.23"
    )

    second = PriceShock(
        token_id="456",
        market_id="100",
        outcome_name="Down",
        previous_timestamp_ms=70000,
        current_timestamp_ms=100200,
        previous_midpoint=Decimal("0.30"),
        current_midpoint=Decimal("0.53"),
        change=Decimal("0.23"),
    )

    events = consolidate_market_shocks(
        [first, second]
    )

    assert len(events) == 2


def test_outcome_cannot_match_twice():
    shocks = [
        make_shock("123", "Up", 100000, "-0.23"),
        make_shock("456", "Down", 100200, "0.23"),
        make_shock("789", "Down", 100300, "0.23"),
    ]

    events = consolidate_market_shocks(shocks)

    assert len(events) == 2
    assert sorted(
        len(event.outcome_shocks)
        for event in events
    ) == [1, 2]


def test_invalid_magnitude_tolerance():
    with pytest.raises(ValueError):
        consolidate_market_shocks(
            [],
            magnitude_tolerance=Decimal("-0.01"),
        )
