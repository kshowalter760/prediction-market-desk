
from decimal import Decimal

import pytest

from prediction_desk.canonical_liquidity import (
    CanonicalLiquidityEvent,
)
from prediction_desk.normalized_liquidity import (
    normalize_outcome_side,
)


def make_pair(timestamp, size, row_id):
    return CanonicalLiquidityEvent(
        market_id="42",
        timestamp_ms=timestamp,
        first_row_id=row_id,
        second_row_id=row_id + 1,
        first_token_id="111",
        second_token_id="222",
        first_outcome="Up",
        second_outcome="Down",
        first_side="BUY",
        second_side="SELL",
        first_price=Decimal("0.45"),
        second_price=Decimal("0.55"),
        size=Decimal(size),
    )


def test_up_buy_normalization():
    events = [
        make_pair(1000, "100", 1),
        make_pair(2000, "150", 3),
        make_pair(3000, "120", 5),
    ]

    report = normalize_outcome_side(events)

    assert report.normalized_updates == 3
    assert report.excluded_events == 0
    assert report.summary["baseline"] == 1
    assert report.summary["addition"] == 1
    assert report.summary["reduction"] == 1
    assert report.summary["total_added"] == Decimal("50")
    assert report.summary["total_reduced"] == Decimal("30")


def test_complementary_side_not_double_counted():
    events = [
        make_pair(1000, "100", 1),
        make_pair(2000, "150", 3),
    ]

    report = normalize_outcome_side(events)

    assert report.normalized_updates == 2
    assert report.summary["total_added"] == Decimal("50")


def test_missing_outcome_side_is_reported():
    events = [make_pair(1000, "100", 1)]

    report = normalize_outcome_side(
        events,
        outcome="Up",
        side="SELL",
    )

    assert report.normalized_updates == 0
    assert report.excluded_events == 1
    assert report.movements == []


def test_multiple_markets_rejected():
    first = make_pair(1000, "100", 1)
    second = make_pair(2000, "150", 3)

    from dataclasses import replace

    second = replace(second, market_id="99")

    with pytest.raises(ValueError, match="one market"):
        normalize_outcome_side([first, second])


def test_empty_events_rejected():
    with pytest.raises(ValueError, match="No canonical"):
        normalize_outcome_side([])
