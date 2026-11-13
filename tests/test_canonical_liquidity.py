
from decimal import Decimal

import pytest

from prediction_desk.canonical_liquidity import (
    RawLiquidityUpdate,
    pair_liquidity_updates,
)


def make_update(
    row_id,
    token_id,
    outcome,
    side,
    price,
    size="100",
    timestamp=1000,
    market_id="42",
):
    return RawLiquidityUpdate(
        row_id=row_id,
        market_id=market_id,
        token_id=token_id,
        outcome_name=outcome,
        timestamp_ms=timestamp,
        side=side,
        price=Decimal(price),
        size=Decimal(size),
    )


def test_complementary_pair():
    updates = [
        make_update(1, "111", "Up", "BUY", "0.45"),
        make_update(2, "222", "Down", "SELL", "0.55"),
    ]

    result = pair_liquidity_updates(updates)

    assert len(result.events) == 1
    assert result.unmatched_ids == []
    assert result.ambiguous_ids == []

    event = result.events[0]
    assert event.first_row_id == 1
    assert event.second_row_id == 2
    assert event.size == Decimal("100")


def test_different_markets_do_not_pair():
    updates = [
        make_update(1, "111", "Up", "BUY", "0.45"),
        make_update(
            2, "222", "Down", "SELL",
            "0.55", market_id="99",
        ),
    ]

    result = pair_liquidity_updates(updates)

    assert len(result.events) == 0
    assert result.unmatched_ids == [1, 2]


def test_mismatched_size_does_not_pair():
    updates = [
        make_update(1, "111", "Up", "BUY", "0.45"),
        make_update(
            2, "222", "Down", "SELL",
            "0.55", size="200",
        ),
    ]

    result = pair_liquidity_updates(updates)

    assert len(result.events) == 0
    assert result.unmatched_ids == [1, 2]


def test_same_side_does_not_pair():
    updates = [
        make_update(1, "111", "Up", "BUY", "0.45"),
        make_update(2, "222", "Down", "BUY", "0.55"),
    ]

    result = pair_liquidity_updates(updates)

    assert len(result.events) == 0


def test_different_timestamps_do_not_pair():
    updates = [
        make_update(1, "111", "Up", "BUY", "0.45"),
        make_update(
            2, "222", "Down", "SELL",
            "0.55", timestamp=2000,
        ),
    ]

    result = pair_liquidity_updates(updates)

    assert len(result.events) == 0


def test_ambiguous_pairs_are_excluded():
    updates = [
        make_update(1, "111", "Up", "BUY", "0.45"),
        make_update(2, "222", "Down", "SELL", "0.55"),
        make_update(3, "333", "Down", "SELL", "0.55"),
    ]

    result = pair_liquidity_updates(updates)

    assert len(result.events) == 0
    assert result.ambiguous_ids == [1, 2, 3]


def test_duplicate_source_ids_rejected():
    updates = [
        make_update(1, "111", "Up", "BUY", "0.45"),
        make_update(1, "222", "Down", "SELL", "0.55"),
    ]

    with pytest.raises(ValueError, match="Duplicate"):
        pair_liquidity_updates(updates)


def test_multiple_pairs_same_timestamp():
    updates = [
        make_update(1, "111", "Up", "BUY", "0.45"),
        make_update(2, "222", "Down", "SELL", "0.55"),
        make_update(3, "111", "Up", "BUY", "0.46"),
        make_update(4, "222", "Down", "SELL", "0.54"),
    ]

    result = pair_liquidity_updates(updates)

    assert len(result.events) == 2
    assert result.unmatched_ids == []
    assert result.ambiguous_ids == []
