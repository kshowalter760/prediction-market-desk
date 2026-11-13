
from decimal import Decimal

import pytest

from prediction_desk.checkpoint_research import (
    CheckpointResearchRow,
)
from prediction_desk.checkpoint_quality import (
    audit_checkpoint_quality,
)


D = Decimal


def make_row(
    timestamp_ms,
    *,
    token_id="123",
    session_id=5,
    status="aligned",
    spot_age_ms=100,
):
    return CheckpointResearchRow(
        token_id=token_id,
        session_id=session_id,
        timestamp_ms=timestamp_ms,
        message_sequence=timestamp_ms,
        alignment_status=status,
        spot_price_usd=(
            D("78000") if status == "aligned" else None
        ),
        spot_age_ms=(
            spot_age_ms if status == "aligned" else None
        ),
        spot_return_pct=None,
        polymarket_mid_price=D("0.50"),
        polymarket_mid_change=None,
        polymarket_spread=D("0.01"),
        polymarket_imbalance=D("0"),
    )


def regular_rows():
    return [
        make_row(100000),
        make_row(130000),
        make_row(160000),
        make_row(190000),
        make_row(220000),
    ]


def test_regular_checkpoint_intervals():
    report = audit_checkpoint_quality(regular_rows())

    assert report.unique_timestamps == 5
    assert report.minimum_interval_ms == 30000
    assert report.maximum_interval_ms == 30000
    assert report.long_gap_count == 0


def test_long_gap_detected():
    rows = [
        make_row(100000),
        make_row(130000),
        make_row(220001),
    ]

    report = audit_checkpoint_quality(rows)

    assert report.long_gap_count == 1
    assert "Long checkpoint gaps detected" in report.warnings


def test_gap_threshold_is_exclusive():
    rows = [
        make_row(100000),
        make_row(160000),
    ]

    report = audit_checkpoint_quality(rows)

    assert report.long_gap_count == 0


def test_stale_and_missing_counts():
    rows = [
        make_row(100000),
        make_row(130000, status="stale_spot"),
        make_row(160000, status="missing_spot"),
    ]

    report = audit_checkpoint_quality(rows)

    assert report.aligned_count == 1
    assert report.stale_count == 1
    assert report.missing_count == 1
    assert not report.research_ready
    assert "Not all observations are aligned" in report.warnings


def test_shared_outcome_timestamps():
    rows = [
        make_row(100000, token_id="123"),
        make_row(100000, token_id="456"),
        make_row(130000, token_id="123"),
        make_row(130000, token_id="456"),
    ]

    report = audit_checkpoint_quality(rows)

    assert report.row_count == 4
    assert report.token_count == 2
    assert report.unique_timestamps == 2
    assert any(
        "not independent market observations" in warning
        for warning in report.warnings
    )


def test_unverified_replay_blocks_readiness():
    report = audit_checkpoint_quality(regular_rows())

    assert not report.independent_replay_verified
    assert not report.research_ready
    assert any(
        "Independent replay verification" in warning
        for warning in report.warnings
    )


def test_verified_clean_dataset_passes_basic_gate():
    report = audit_checkpoint_quality(
        regular_rows(),
        independent_replay_verified=True,
    )

    assert report.research_ready
    assert report.aligned_count == 5
    assert report.long_gap_count == 0


def test_maximum_spot_age():
    rows = [
        make_row(100000, spot_age_ms=50),
        make_row(130000, spot_age_ms=1028),
        make_row(160000, spot_age_ms=400),
    ]

    report = audit_checkpoint_quality(rows)

    assert report.maximum_spot_age_ms == 1028


def test_empty_dataset_rejected():
    with pytest.raises(ValueError, match="empty dataset"):
        audit_checkpoint_quality([])


def test_mixed_sessions_rejected():
    rows = [
        make_row(100000, session_id=5),
        make_row(130000, session_id=6),
    ]

    with pytest.raises(ValueError, match="one session"):
        audit_checkpoint_quality(rows)


def test_invalid_expected_interval():
    with pytest.raises(ValueError, match="Invalid expected interval"):
        audit_checkpoint_quality(
            regular_rows(),
            expected_interval_ms=0,
        )


def test_invalid_gap_multiplier():
    with pytest.raises(ValueError, match="Invalid gap multiplier"):
        audit_checkpoint_quality(
            regular_rows(),
            gap_multiplier=0,
        )
