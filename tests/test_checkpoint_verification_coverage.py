
import sqlite3
from decimal import Decimal

import pytest

from prediction_desk.checkpoint_research import (
    CheckpointResearchRow,
)
from prediction_desk.checkpoint_verification_coverage import (
    CheckpointCoverage,
    CoverageReport,
    evaluate_checkpoint_coverage,
)
from prediction_desk.snapshot_pair_report import (
    PairResult,
    SessionVerificationReport,
)


SESSION_ID = 3
TOKEN_A = "token_a"
TOKEN_B = "token_b"


@pytest.fixture
def connection():
    db = sqlite3.connect(":memory:")

    db.execute(
        """
        CREATE TABLE order_book_snapshots (
            id INTEGER PRIMARY KEY,
            token_id TEXT,
            stream_session_id INTEGER,
            message_sequence INTEGER,
            source_timestamp_ms INTEGER
        )
        """
    )

    yield db
    db.close()


def add_snapshot(
    connection,
    snapshot_id,
    token_id=TOKEN_A,
    session_id=SESSION_ID,
    sequence=10,
    timestamp_ms=1000,
):
    connection.execute(
        """
        INSERT INTO order_book_snapshots (
            id,
            token_id,
            stream_session_id,
            message_sequence,
            source_timestamp_ms
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            token_id,
            session_id,
            sequence,
            timestamp_ms,
        ),
    )


def add_interval(
    connection,
    initial_id=1,
    final_id=2,
    token_id=TOKEN_A,
    session_id=SESSION_ID,
    start_seq=10,
    end_seq=20,
    start_ms=1000,
    end_ms=2000,
):
    add_snapshot(
        connection,
        initial_id,
        token_id,
        session_id,
        start_seq,
        start_ms,
    )

    add_snapshot(
        connection,
        final_id,
        token_id,
        session_id,
        end_seq,
        end_ms,
    )


def make_row(
    token_id=TOKEN_A,
    session_id=SESSION_ID,
    timestamp_ms=1500,
    sequence=15,
):
    return CheckpointResearchRow(
        token_id=token_id,
        session_id=session_id,
        timestamp_ms=timestamp_ms,
        message_sequence=sequence,
        alignment_status="aligned",
        spot_price_usd=Decimal("78000"),
        spot_age_ms=100,
        spot_return_pct=None,
        polymarket_mid_price=Decimal("0.50"),
        polymarket_mid_change=None,
        polymarket_spread=Decimal("0.01"),
        polymarket_imbalance=Decimal("0"),
    )


def make_pair(
    initial_id=1,
    final_id=2,
    token_id=TOKEN_A,
    session_id=SESSION_ID,
    status="matched",
):
    return PairResult(
        initial_snapshot_id=initial_id,
        final_snapshot_id=final_id,
        token_id=token_id,
        session_id=session_id,
        status=status,
        updates_applied=5,
        error=None,
    )


def make_report(
    *pairs,
    session_id=SESSION_ID,
):
    return SessionVerificationReport(
        session_id=session_id,
        snapshot_count=2 * len(pairs),
        token_count=len({p.token_id for p in pairs}),
        eligible_pair_count=len(pairs),
        matched_pair_count=sum(
            p.status == "matched" for p in pairs
        ),
        mismatched_pair_count=sum(
            p.status == "mismatched" for p in pairs
        ),
        error_count=sum(
            p.status == "error" for p in pairs
        ),
        results=tuple(pairs),
    )


def test_checkpoint_inside_matched_interval(connection):
    add_interval(connection)

    result = evaluate_checkpoint_coverage(
        connection,
        [make_row()],
        make_report(make_pair()),
    )

    assert isinstance(result, CoverageReport)
    assert result.session_id == SESSION_ID
    assert result.checkpoint_count == 1
    assert result.covered_count == 1
    assert result.uncovered_count == 0
    assert result.all_checkpoints_covered is True

    checkpoint = result.checkpoints[0]

    assert isinstance(checkpoint, CheckpointCoverage)
    assert checkpoint.covered is True
    assert checkpoint.initial_snapshot_id == 1
    assert checkpoint.final_snapshot_id == 2


def test_checkpoint_before_interval_is_uncovered(connection):
    add_interval(connection)

    result = evaluate_checkpoint_coverage(
        connection,
        [make_row(timestamp_ms=500, sequence=5)],
        make_report(make_pair()),
    )

    assert result.covered_count == 0
    assert result.uncovered_count == 1
    assert result.all_checkpoints_covered is False


def test_checkpoint_after_interval_is_uncovered(connection):
    add_interval(connection)

    result = evaluate_checkpoint_coverage(
        connection,
        [make_row(timestamp_ms=2500, sequence=25)],
        make_report(make_pair()),
    )

    assert result.checkpoints[0].covered is False


def test_different_token_is_uncovered(connection):
    add_interval(connection)

    result = evaluate_checkpoint_coverage(
        connection,
        [make_row(token_id=TOKEN_B)],
        make_report(make_pair()),
    )

    assert result.checkpoints[0].covered is False
    assert result.checkpoints[0].initial_snapshot_id is None
    assert result.checkpoints[0].final_snapshot_id is None


@pytest.mark.parametrize(
    "sequence",
    [9, 21],
)
def test_sequence_outside_interval_is_uncovered(
    connection,
    sequence,
):
    add_interval(connection)

    result = evaluate_checkpoint_coverage(
        connection,
        [make_row(sequence=sequence)],
        make_report(make_pair()),
    )

    assert result.covered_count == 0


@pytest.mark.parametrize(
    "timestamp_ms",
    [999, 2001],
)
def test_timestamp_outside_interval_is_uncovered(
    connection,
    timestamp_ms,
):
    add_interval(connection)

    result = evaluate_checkpoint_coverage(
        connection,
        [make_row(timestamp_ms=timestamp_ms)],
        make_report(make_pair()),
    )

    assert result.covered_count == 0


def test_multiple_tokens_can_be_covered(connection):
    add_interval(connection)

    add_interval(
        connection,
        initial_id=3,
        final_id=4,
        token_id=TOKEN_B,
    )

    rows = [
        make_row(token_id=TOKEN_A),
        make_row(token_id=TOKEN_B),
    ]

    report = make_report(
        make_pair(),
        make_pair(
            initial_id=3,
            final_id=4,
            token_id=TOKEN_B,
        ),
    )

    result = evaluate_checkpoint_coverage(
        connection,
        rows,
        report,
    )

    assert result.checkpoint_count == 2
    assert result.covered_count == 2
    assert result.uncovered_count == 0
    assert result.all_checkpoints_covered is True

    assert result.checkpoints[0].initial_snapshot_id == 1
    assert result.checkpoints[1].initial_snapshot_id == 3


def test_mixed_covered_and_uncovered_checkpoints(connection):
    add_interval(connection)

    rows = [
        make_row(sequence=15, timestamp_ms=1500),
        make_row(sequence=25, timestamp_ms=2500),
        make_row(token_id=TOKEN_B),
    ]

    result = evaluate_checkpoint_coverage(
        connection,
        rows,
        make_report(make_pair()),
    )

    assert result.checkpoint_count == 3
    assert result.covered_count == 1
    assert result.uncovered_count == 2
    assert result.all_checkpoints_covered is False

    assert [c.covered for c in result.checkpoints] == [
        True,
        False,
        False,
    ]


def test_zero_matched_pairs_provides_no_coverage(connection):
    result = evaluate_checkpoint_coverage(
        connection,
        [make_row()],
        make_report(),
    )

    assert result.checkpoint_count == 1
    assert result.covered_count == 0
    assert result.uncovered_count == 1
    assert result.all_checkpoints_covered is False


def test_mismatched_pair_does_not_confer_coverage(connection):
    add_interval(connection)

    result = evaluate_checkpoint_coverage(
        connection,
        [make_row()],
        make_report(make_pair(status="mismatched")),
    )

    assert result.covered_count == 0
    assert result.checkpoints[0].covered is False


def test_empty_research_dataset_is_rejected(connection):
    with pytest.raises(
        ValueError,
        match="Cannot evaluate empty checkpoint dataset",
    ):
        evaluate_checkpoint_coverage(
            connection,
            [],
            make_report(),
        )


def test_session_mismatch_is_rejected(connection):
    with pytest.raises(ValueError, match="Session mismatch"):
        evaluate_checkpoint_coverage(
            connection,
            [make_row(session_id=5)],
            make_report(session_id=3),
        )


def test_mixed_research_sessions_are_rejected(connection):
    rows = [
        make_row(session_id=3),
        make_row(session_id=5),
    ]

    with pytest.raises(ValueError, match="Session mismatch"):
        evaluate_checkpoint_coverage(
            connection,
            rows,
            make_report(session_id=3),
        )


def test_missing_snapshot_is_rejected(connection):
    add_snapshot(connection, snapshot_id=1)

    with pytest.raises(
        ValueError,
        match="Verification snapshot not found",
    ):
        evaluate_checkpoint_coverage(
            connection,
            [make_row()],
            make_report(make_pair()),
        )


@pytest.mark.parametrize(
    "start_seq,end_seq",
    [
        (20, 10),
        (10, 10),
        (None, 20),
        (10, None),
    ],
)
def test_invalid_snapshot_sequences_are_rejected(
    connection,
    start_seq,
    end_seq,
):
    add_interval(
        connection,
        start_seq=start_seq,
        end_seq=end_seq,
    )

    with pytest.raises(
        ValueError,
        match="Invalid verification interval",
    ):
        evaluate_checkpoint_coverage(
            connection,
            [make_row()],
            make_report(make_pair()),
        )


def test_reversed_snapshot_timestamps_are_rejected(connection):
    add_interval(
        connection,
        start_ms=2000,
        end_ms=1000,
    )

    with pytest.raises(
        ValueError,
        match="Invalid verification interval",
    ):
        evaluate_checkpoint_coverage(
            connection,
            [make_row()],
            make_report(make_pair()),
        )


def test_snapshot_token_mismatch_is_rejected(connection):
    add_snapshot(
        connection,
        snapshot_id=1,
        token_id=TOKEN_A,
        sequence=10,
        timestamp_ms=1000,
    )

    add_snapshot(
        connection,
        snapshot_id=2,
        token_id=TOKEN_B,
        sequence=20,
        timestamp_ms=2000,
    )

    with pytest.raises(
        ValueError,
        match="Invalid verification interval",
    ):
        evaluate_checkpoint_coverage(
            connection,
            [make_row()],
            make_report(make_pair()),
        )


def test_snapshot_session_mismatch_is_rejected(connection):
    add_interval(
        connection,
        session_id=5,
    )

    with pytest.raises(
        ValueError,
        match="Invalid verification interval",
    ):
        evaluate_checkpoint_coverage(
            connection,
            [make_row()],
            make_report(make_pair()),
        )


@pytest.mark.parametrize(
    "sequence,timestamp_ms",
    [
        (10, 1000),
        (20, 2000),
    ],
)
def test_interval_boundaries_are_inclusive(
    connection,
    sequence,
    timestamp_ms,
):
    add_interval(connection)

    result = evaluate_checkpoint_coverage(
        connection,
        [
            make_row(
                sequence=sequence,
                timestamp_ms=timestamp_ms,
            )
        ],
        make_report(make_pair()),
    )

    assert result.covered_count == 1
    assert result.all_checkpoints_covered is True


def test_noninteger_checkpoint_sequence_is_uncovered(connection):
    add_interval(connection)

    result = evaluate_checkpoint_coverage(
        connection,
        [make_row(sequence=15.0)],
        make_report(make_pair()),
    )

    assert result.covered_count == 0
    assert result.checkpoints[0].covered is False


def test_boolean_checkpoint_sequence_is_uncovered(connection):
    add_interval(connection)

    result = evaluate_checkpoint_coverage(
        connection,
        [make_row(sequence=True)],
        make_report(make_pair()),
    )

    assert result.covered_count == 0


def test_complete_coverage_flag(connection):
    add_interval(connection)

    rows = [
        make_row(sequence=12, timestamp_ms=1200),
        make_row(sequence=15, timestamp_ms=1500),
        make_row(sequence=18, timestamp_ms=1800),
    ]

    result = evaluate_checkpoint_coverage(
        connection,
        rows,
        make_report(make_pair()),
    )

    assert result.checkpoint_count == 3
    assert result.covered_count == 3
    assert result.uncovered_count == 0
    assert result.all_checkpoints_covered is True


def test_partial_coverage_flag(connection):
    add_interval(connection)

    rows = [
        make_row(sequence=15, timestamp_ms=1500),
        make_row(sequence=25, timestamp_ms=2500),
    ]

    result = evaluate_checkpoint_coverage(
        connection,
        rows,
        make_report(make_pair()),
    )

    assert result.checkpoint_count == 2
    assert result.covered_count == 1
    assert result.uncovered_count == 1
    assert result.all_checkpoints_covered is False


def test_uncovered_checkpoint_has_no_snapshot_ids(connection):
    add_interval(connection)

    result = evaluate_checkpoint_coverage(
        connection,
        [make_row(sequence=25, timestamp_ms=2500)],
        make_report(make_pair()),
    )

    checkpoint = result.checkpoints[0]

    assert checkpoint.covered is False
    assert checkpoint.initial_snapshot_id is None
    assert checkpoint.final_snapshot_id is None


def test_unrelated_mismatched_pair_is_ignored(connection):
    add_interval(connection)

    report = make_report(
        make_pair(),
        make_pair(
            initial_id=99,
            final_id=100,
            token_id=TOKEN_B,
            status="mismatched",
        ),
    )

    result = evaluate_checkpoint_coverage(
        connection,
        [make_row()],
        report,
    )

    assert result.covered_count == 1
    assert result.checkpoints[0].initial_snapshot_id == 1
    assert result.checkpoints[0].final_snapshot_id == 2
