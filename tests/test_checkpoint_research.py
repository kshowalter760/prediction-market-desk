
from dataclasses import replace
from decimal import Decimal

import pytest

from prediction_desk.cross_market_alignment import (
    AlignedObservation,
)
from prediction_desk.checkpoint_research import (
    build_checkpoint_research,
)


D = Decimal


def make_observation(
    *,
    token_id="123",
    session_id=5,
    timestamp_ms=1000,
    sequence=1,
    spot_price="100",
    mid_price="0.50",
    status="aligned",
):
    return AlignedObservation(
        token_id=token_id,
        session_id=session_id,
        checkpoint_timestamp_ms=timestamp_ms,
        message_sequence=sequence,
        polymarket_mid_price=(
            D(mid_price) if mid_price is not None else None
        ),
        polymarket_spread=D("0.02"),
        polymarket_imbalance=D("0"),
        spot_trade_id=1 if spot_price is not None else None,
        spot_timestamp_ms=(
            timestamp_ms - 100
            if spot_price is not None
            else None
        ),
        spot_price_usd=(
            D(spot_price) if spot_price is not None else None
        ),
        spot_age_ms=100 if spot_price is not None else None,
        alignment_status=status,
    )


def test_empty_dataset():
    assert build_checkpoint_research([]) == []


def test_spot_return_calculation():
    first = make_observation()
    second = make_observation(
        timestamp_ms=2000,
        sequence=2,
        spot_price="110",
    )

    rows = build_checkpoint_research([first, second])

    assert rows[0].spot_return_pct is None
    assert rows[1].spot_return_pct == D("10")


def test_negative_spot_return():
    first = make_observation(spot_price="100")
    second = make_observation(
        timestamp_ms=2000,
        sequence=2,
        spot_price="90",
    )

    rows = build_checkpoint_research([first, second])

    assert rows[1].spot_return_pct == D("-10")


def test_complementary_outcomes_share_spot_return():
    observations = [
        make_observation(token_id="123"),
        make_observation(token_id="456", mid_price="0.50"),
        make_observation(
            token_id="123",
            timestamp_ms=2000,
            sequence=2,
            spot_price="105",
            mid_price="0.51",
        ),
        make_observation(
            token_id="456",
            timestamp_ms=2000,
            sequence=2,
            spot_price="105",
            mid_price="0.49",
        ),
    ]

    rows = build_checkpoint_research(observations)

    later = [
        row for row in rows
        if row.timestamp_ms == 2000
    ]

    assert len(later) == 2
    assert all(
        row.spot_return_pct == D("5")
        for row in later
    )

    changes = {
        row.token_id: row.polymarket_mid_change
        for row in later
    }

    assert changes["123"] == D("0.01")
    assert changes["456"] == D("-0.01")


def test_chronological_ordering():
    first = make_observation()
    second = make_observation(
        timestamp_ms=2000,
        sequence=2,
        spot_price="110",
    )

    rows = build_checkpoint_research([second, first])

    assert [row.timestamp_ms for row in rows] == [
        1000, 2000
    ]
    assert rows[1].spot_return_pct == D("10")


def test_stale_spot_excluded():
    first = make_observation()

    stale = make_observation(
        timestamp_ms=2000,
        sequence=2,
        spot_price="120",
        status="stale_spot",
    )

    third = make_observation(
        timestamp_ms=3000,
        sequence=3,
        spot_price="110",
    )

    rows = build_checkpoint_research(
        [first, stale, third]
    )

    assert rows[1].spot_price_usd is None
    assert rows[1].spot_return_pct is None
    assert rows[2].spot_return_pct == D("10")


def test_conflicting_spot_prices_rejected():
    first = make_observation(token_id="123")

    conflicting = make_observation(
        token_id="456",
        spot_price="101",
    )

    with pytest.raises(
        ValueError,
        match="Conflicting spot prices",
    ):
        build_checkpoint_research([first, conflicting])


def test_duplicate_checkpoint_rejected():
    observation = make_observation()

    with pytest.raises(
        ValueError,
        match="Duplicate checkpoint",
    ):
        build_checkpoint_research(
            [observation, observation]
        )


def test_mixed_sessions_rejected():
    first = make_observation(session_id=5)

    second = make_observation(
        session_id=6,
        timestamp_ms=2000,
    )

    with pytest.raises(
        ValueError,
        match="one session",
    ):
        build_checkpoint_research([first, second])


def test_invalid_spot_price_rejected():
    observation = make_observation(
        spot_price="0"
    )

    with pytest.raises(
        ValueError,
        match="Invalid aligned spot price",
    ):
        build_checkpoint_research([observation])


def test_missing_spot_observation():
    observation = make_observation(
        spot_price=None,
        status="missing_spot",
    )

    rows = build_checkpoint_research([observation])

    assert len(rows) == 1
    assert rows[0].spot_price_usd is None
    assert rows[0].spot_return_pct is None


def test_decimal_midpoint_precision():
    first = make_observation(mid_price="0.501")
    second = make_observation(
        timestamp_ms=2000,
        sequence=2,
        mid_price="0.502",
    )

    rows = build_checkpoint_research([first, second])

    assert rows[1].polymarket_mid_change == D("0.001")
    assert isinstance(
        rows[1].polymarket_mid_change,
        Decimal,
    )
