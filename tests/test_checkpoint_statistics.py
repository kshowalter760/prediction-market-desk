
from dataclasses import replace
from decimal import Decimal

import pytest

from prediction_desk.checkpoint_research import (
    CheckpointResearchRow,
)
from prediction_desk.checkpoint_statistics import (
    pearson_correlation,
    summarize_token,
)


D = Decimal


def make_row(
    timestamp,
    spot_return,
    mid_change,
    token_id="123",
):
    return CheckpointResearchRow(
        token_id=token_id,
        session_id=5,
        timestamp_ms=timestamp,
        message_sequence=timestamp,
        alignment_status="aligned",
        spot_price_usd=D("78000"),
        spot_age_ms=100,
        spot_return_pct=(
            D(str(spot_return))
            if spot_return is not None else None
        ),
        polymarket_mid_price=D("0.50"),
        polymarket_mid_change=(
            D(str(mid_change))
            if mid_change is not None else None
        ),
        polymarket_spread=D("0.01"),
        polymarket_imbalance=D("0"),
    )


def test_perfect_positive_correlation():
    result, status = pearson_correlation(
        [D("1"), D("2"), D("3"), D("4"), D("5")],
        [D("2"), D("4"), D("6"), D("8"), D("10")],
    )

    assert result == pytest.approx(1.0)
    assert status == "calculated"


def test_perfect_negative_correlation():
    result, status = pearson_correlation(
        [D("1"), D("2"), D("3"), D("4"), D("5")],
        [D("5"), D("4"), D("3"), D("2"), D("1")],
    )

    assert result == pytest.approx(-1.0)
    assert status == "calculated"


def test_zero_variance():
    result, status = pearson_correlation(
        [D("1"), D("2"), D("3"), D("4"), D("5")],
        [D("0")] * 5,
    )

    assert result is None
    assert status == "zero_variance"


def test_insufficient_samples():
    result, status = pearson_correlation(
        [D("1"), D("2")],
        [D("2"), D("3")],
    )

    assert result is None
    assert status == "insufficient_samples"


def test_mismatched_series():
    with pytest.raises(ValueError, match="Series lengths"):
        pearson_correlation(
            [D("1")],
            [D("1"), D("2")],
        )


def test_descriptive_statistics():
    rows = [
        make_row(1000, None, None),
        make_row(2000, 2, 0),
        make_row(3000, -4, 0.01),
    ]

    result = summarize_token(rows)

    assert result.checkpoint_count == 3
    assert result.aligned_count == 3
    assert result.spot_return_count == 2
    assert result.midpoint_change_events == 1
    assert result.average_absolute_spot_return_pct == D("3")
    assert result.maximum_absolute_spot_return_pct == D("4")
    assert result.average_absolute_midpoint_change == D("0.005")
    assert result.correlation_status == "insufficient_samples"


def test_mixed_tokens_rejected():
    rows = [
        make_row(1000, None, None),
        make_row(2000, 1, 0.01, token_id="456"),
    ]

    with pytest.raises(ValueError, match="one token"):
        summarize_token(rows)


def test_empty_rows_rejected():
    with pytest.raises(ValueError, match="At least one row"):
        summarize_token([])
