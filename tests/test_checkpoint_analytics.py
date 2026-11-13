
from dataclasses import replace
from decimal import Decimal

import pytest

from prediction_desk.book_reconstruction import (
    BookReconstructor,
)
from prediction_desk.replay_checkpoints import (
    ReplayCheckpoint,
)
from prediction_desk.checkpoint_analytics import (
    observation_from_checkpoint,
    summarize_checkpoints,
)


D = Decimal


def make_checkpoint(
    *,
    token_id="123",
    session_id=5,
    timestamp_ms=1000,
    sequence=2,
    bids=None,
    asks=None,
):
    if bids is None:
        bids = [(D("0.49"), D("100"))]

    if asks is None:
        asks = [(D("0.51"), D("100"))]

    book = BookReconstructor(
        timestamp_ms=timestamp_ms,
        bids=bids,
        asks=asks,
    ).state()

    return ReplayCheckpoint(
        token_id=token_id,
        session_id=session_id,
        message_sequence=sequence,
        timestamp_ms=timestamp_ms,
        updates_applied=1,
        book=book,
    )


def make_observation(**kwargs):
    return observation_from_checkpoint(
        make_checkpoint(**kwargs)
    )


def test_checkpoint_observation_metrics():
    observation = make_observation(
        bids=[(D("0.49"), D("150"))],
        asks=[(D("0.51"), D("50"))],
    )

    assert observation.best_bid == D("0.49")
    assert observation.best_ask == D("0.51")
    assert observation.spread == D("0.02")
    assert observation.mid_price == D("0.50")
    assert observation.bid_depth == D("150")
    assert observation.ask_depth == D("50")
    assert observation.total_depth == D("200")
    assert observation.imbalance == D("0.5")


def test_summary_averages():
    first = make_observation(
        timestamp_ms=1000,
        bids=[(D("0.49"), D("150"))],
        asks=[(D("0.51"), D("50"))],
    )

    second = make_observation(
        timestamp_ms=2000,
        sequence=3,
        bids=[(D("0.48"), D("50"))],
        asks=[(D("0.52"), D("150"))],
    )

    summary = summarize_checkpoints([first, second])

    assert summary.observation_count == 2
    assert summary.average_spread == D("0.03")
    assert summary.minimum_spread == D("0.02")
    assert summary.maximum_spread == D("0.04")
    assert summary.average_total_depth == D("200")
    assert summary.average_imbalance == D("0")
    assert summary.mid_price_change == D("0")


def test_mid_price_change_uses_chronological_order():
    early = make_observation(
        timestamp_ms=1000,
        sequence=2,
        bids=[(D("0.39"), D("100"))],
        asks=[(D("0.41"), D("100"))],
    )

    late = make_observation(
        timestamp_ms=2000,
        sequence=3,
        bids=[(D("0.59"), D("100"))],
        asks=[(D("0.61"), D("100"))],
    )

    summary = summarize_checkpoints([late, early])

    assert summary.first_mid_price == D("0.40")
    assert summary.last_mid_price == D("0.60")
    assert summary.mid_price_change == D("0.20")


def test_missing_quotes_handled():
    observation = make_observation(
        bids=[],
        asks=[],
    )

    assert observation.mid_price is None
    assert observation.spread is None
    assert observation.total_depth == D("0")
    assert observation.imbalance is None

    summary = summarize_checkpoints([observation])

    assert summary.average_spread is None
    assert summary.average_imbalance is None
    assert summary.first_mid_price is None
    assert summary.last_mid_price is None
    assert summary.mid_price_change is None


def test_empty_observations_rejected():
    with pytest.raises(
        ValueError,
        match="No liquidity observations",
    ):
        summarize_checkpoints([])


def test_mixed_tokens_rejected():
    first = make_observation(token_id="123")
    second = make_observation(token_id="456")

    with pytest.raises(
        ValueError,
        match="Mixed token or session",
    ):
        summarize_checkpoints([first, second])


def test_mixed_sessions_rejected():
    first = make_observation(session_id=5)
    second = make_observation(session_id=6)

    with pytest.raises(
        ValueError,
        match="Mixed token or session",
    ):
        summarize_checkpoints([first, second])


def test_decimal_precision_preserved():
    observation = make_observation(
        bids=[(D("0.491"), D("0.1"))],
        asks=[(D("0.509"), D("0.2"))],
    )

    assert observation.mid_price == D("0.500")
    assert observation.spread == D("0.018")
    assert observation.total_depth == D("0.3")
    assert isinstance(observation.total_depth, Decimal)
