
import pandas as pd
import pytest

from prediction_desk.dashboard_data import summarize_price_history


def make_history(
    timestamps,
    bids,
    asks,
):
    """Create a minimal price-history DataFrame."""
    return pd.DataFrame(
        {
            "observed_at_utc": timestamps,
            "best_bid": bids,
            "best_ask": asks,
        }
    )


def test_regular_observation_coverage():
    history = make_history(
        [
            "2026-11-14T12:00:00Z",
            "2026-11-14T12:00:05Z",
            "2026-11-14T12:00:10Z",
        ],
        ["0.40", "0.41", "0.42"],
        ["0.42", "0.43", "0.44"],
    )

    summary = summarize_price_history(history)

    assert summary["total_observations"] == 3
    assert summary["duration_seconds"] == 10.0
    assert summary["largest_gap_seconds"] == 5.0
    assert summary["missing_bid_count"] == 0
    assert summary["missing_ask_count"] == 0


def test_irregular_observation_gaps():
    history = make_history(
        [
            "2026-11-14T12:00:00Z",
            "2026-11-14T12:00:05Z",
            "2026-11-14T12:02:05Z",
        ],
        [0.40, 0.41, 0.42],
        [0.42, 0.43, 0.44],
    )

    summary = summarize_price_history(history)

    assert summary["duration_seconds"] == 125.0
    assert summary["largest_gap_seconds"] == 120.0


def test_missing_quotes():
    history = make_history(
        [
            "2026-11-14T12:00:00Z",
            "2026-11-14T12:00:05Z",
            "2026-11-14T12:00:10Z",
        ],
        ["0.40", None, "invalid"],
        [None, "0.43", "0.44"],
    )

    summary = summarize_price_history(history)

    assert summary["missing_bid_count"] == 2
    assert summary["missing_ask_count"] == 1


def test_single_observation():
    history = make_history(
        ["2026-11-14T12:00:00Z"],
        ["0.40"],
        ["0.42"],
    )

    summary = summarize_price_history(history)

    assert summary["total_observations"] == 1
    assert summary["duration_seconds"] == 0.0
    assert summary["largest_gap_seconds"] is None


def test_invalid_timestamps():
    history = make_history(
        ["invalid", None],
        ["0.40", "0.41"],
        ["0.42", "0.43"],
    )

    summary = summarize_price_history(history)

    assert summary["total_observations"] == 2
    assert summary["first_observation"] is None
    assert summary["last_observation"] is None
    assert summary["duration_seconds"] is None
    assert summary["largest_gap_seconds"] is None


def test_out_of_order_timestamps():
    history = make_history(
        [
            "2026-11-14T12:00:10Z",
            "2026-11-14T12:00:00Z",
            "2026-11-14T12:00:05Z",
        ],
        [0.42, 0.40, 0.41],
        [0.44, 0.42, 0.43],
    )

    summary = summarize_price_history(history)

    assert summary["duration_seconds"] == 10.0
    assert summary["largest_gap_seconds"] == 5.0


def test_empty_history():
    history = make_history([], [], [])

    summary = summarize_price_history(history)

    assert summary["total_observations"] == 0
    assert summary["first_observation"] is None
    assert summary["last_observation"] is None
    assert summary["duration_seconds"] is None
    assert summary["largest_gap_seconds"] is None
    assert summary["missing_bid_count"] == 0
    assert summary["missing_ask_count"] == 0


@pytest.mark.parametrize(
    "missing_column",
    [
        "observed_at_utc",
        "best_bid",
        "best_ask",
    ],
)
def test_missing_required_columns(missing_column):
    history = make_history(
        ["2026-11-14T12:00:00Z"],
        ["0.40"],
        ["0.42"],
    )

    history = history.drop(columns=[missing_column])

    with pytest.raises(ValueError, match="Missing required columns"):
        summarize_price_history(history)
