
from decimal import Decimal

import pytest

from prediction_desk.liquidity_analytics import (
    LevelUpdate,
    LiquidityTracker,
    analyze_liquidity,
    summarize_liquidity,
)


def make_update(
    timestamp,
    size,
    token_id="123456",
    side="BUY",
    price="0.45",
):
    return LevelUpdate(
        token_id=token_id,
        timestamp_ms=timestamp,
        side=side,
        price=Decimal(price),
        size=Decimal(size),
    )


def test_first_observation_is_baseline():
    tracker = LiquidityTracker()

    result = tracker.process(make_update(1000, "300"))

    assert result.classification == "baseline"
    assert result.previous_size is None
    assert result.size_change is None


def test_liquidity_addition():
    tracker = LiquidityTracker()

    tracker.process(make_update(1000, "300"))
    result = tracker.process(make_update(2000, "450"))

    assert result.classification == "addition"
    assert result.size_change == Decimal("150")


def test_liquidity_reduction():
    tracker = LiquidityTracker()

    tracker.process(make_update(1000, "450"))
    result = tracker.process(make_update(2000, "200"))

    assert result.classification == "reduction"
    assert result.size_change == Decimal("-250")


def test_liquidity_removal():
    tracker = LiquidityTracker()

    tracker.process(make_update(1000, "200"))
    result = tracker.process(make_update(2000, "0"))

    assert result.classification == "removal"
    assert result.size_change == Decimal("-200")


def test_unchanged_size():
    tracker = LiquidityTracker()

    tracker.process(make_update(1000, "200"))
    result = tracker.process(make_update(2000, "200"))

    assert result.classification == "unchanged"
    assert result.size_change == Decimal("0")


def test_duplicate_observation_ignored():
    tracker = LiquidityTracker()

    tracker.process(make_update(1000, "200"))
    result = tracker.process(make_update(1000, "200"))

    assert result is None


def test_conflicting_duplicate_rejected():
    tracker = LiquidityTracker()

    tracker.process(make_update(1000, "200"))

    with pytest.raises(ValueError, match="Conflicting"):
        tracker.process(make_update(1000, "250"))


def test_out_of_order_timestamp_rejected():
    tracker = LiquidityTracker()

    tracker.process(make_update(2000, "200"))

    with pytest.raises(ValueError, match="timestamp order"):
        tracker.process(make_update(1000, "250"))


def test_tokens_are_independent():
    tracker = LiquidityTracker()

    first = tracker.process(
        make_update(1000, "200", token_id="111")
    )

    second = tracker.process(
        make_update(2000, "300", token_id="222")
    )

    assert first.classification == "baseline"
    assert second.classification == "baseline"


def test_sides_are_independent():
    tracker = LiquidityTracker()

    tracker.process(make_update(1000, "200", side="BUY"))

    result = tracker.process(
        make_update(2000, "300", side="SELL")
    )

    assert result.classification == "baseline"


def test_prices_are_independent():
    tracker = LiquidityTracker()

    tracker.process(make_update(1000, "200", price="0.45"))

    result = tracker.process(
        make_update(2000, "300", price="0.46")
    )

    assert result.classification == "baseline"


def test_summary():
    updates = [
        make_update(1000, "300"),
        make_update(2000, "450"),
        make_update(3000, "200"),
        make_update(4000, "0"),
    ]

    movements = analyze_liquidity(updates)
    summary = summarize_liquidity(movements)

    assert summary["baseline"] == 1
    assert summary["addition"] == 1
    assert summary["reduction"] == 1
    assert summary["removal"] == 1
    assert summary["total_added"] == Decimal("150")
    assert summary["total_reduced"] == Decimal("450")


@pytest.mark.parametrize(
    "price,size",
    [
        ("0", "100"),
        ("1", "100"),
        ("NaN", "100"),
        ("0.45", "-1"),
        ("0.45", "Infinity"),
    ],
)
def test_invalid_values_rejected(price, size):
    tracker = LiquidityTracker()

    update = make_update(
        1000,
        size,
        price=price,
    )

    with pytest.raises(ValueError):
        tracker.process(update)
