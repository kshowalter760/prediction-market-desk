
import sqlite3
from decimal import Decimal

import pytest

import run_checkpoint_research as runner

from prediction_desk.checkpoint_research import (
    CheckpointResearchRow,
)
from prediction_desk.snapshot_pair_report import (
    PairResult,
    SessionVerificationReport,
)


SESSION_ID = 3
TOKEN_ID = "test_token"


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


def add_snapshots(connection):
    connection.executemany(
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
        [
            (1, TOKEN_ID, SESSION_ID, 10, 1000),
            (2, TOKEN_ID, SESSION_ID, 20, 2000),
        ],
    )


def make_row(sequence=15, timestamp_ms=1500):
    return CheckpointResearchRow(
        token_id=TOKEN_ID,
        session_id=SESSION_ID,
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


def make_report(status="matched"):
    pair = PairResult(
        initial_snapshot_id=1,
        final_snapshot_id=2,
        token_id=TOKEN_ID,
        session_id=SESSION_ID,
        status=status,
        updates_applied=10,
        error=None,
    )

    return SessionVerificationReport(
        session_id=SESSION_ID,
        snapshot_count=2,
        token_count=1,
        eligible_pair_count=1,
        matched_pair_count=int(status == "matched"),
        mismatched_pair_count=int(status == "mismatched"),
        error_count=int(
            status in ("error", "invalid_sequence")
        ),
        results=(pair,),
    )


def patch_verifier(monkeypatch, report):
    calls = []

    def fake_verifier(connection, session_id):
        calls.append(session_id)
        return report

    monkeypatch.setattr(
        runner,
        "verify_session_snapshot_pairs",
        fake_verifier,
    )

    return calls


def test_matched_pair_covers_checkpoint(
    connection,
    monkeypatch,
):
    add_snapshots(connection)
    report = make_report("matched")
    calls = patch_verifier(monkeypatch, report)

    verification, coverage = (
        runner.build_verification_evidence(
            connection,
            SESSION_ID,
            [make_row()],
        )
    )

    assert calls == [SESSION_ID]
    assert verification is report
    assert coverage is not None
    assert coverage.checkpoint_count == 1
    assert coverage.covered_count == 1
    assert coverage.uncovered_count == 0
    assert coverage.all_checkpoints_covered is True
    assert coverage.checkpoints[0].initial_snapshot_id == 1
    assert coverage.checkpoints[0].final_snapshot_id == 2


def test_mismatched_pair_does_not_cover_checkpoint(
    connection,
    monkeypatch,
):
    add_snapshots(connection)
    report = make_report("mismatched")
    patch_verifier(monkeypatch, report)

    verification, coverage = (
        runner.build_verification_evidence(
            connection,
            SESSION_ID,
            [make_row()],
        )
    )

    assert verification.mismatched_pair_count == 1
    assert coverage.covered_count == 0
    assert coverage.uncovered_count == 1
    assert coverage.all_checkpoints_covered is False


def test_partial_coverage_preserves_uncovered_rows(
    connection,
    monkeypatch,
):
    add_snapshots(connection)
    patch_verifier(
        monkeypatch,
        make_report("matched"),
    )

    rows = [
        make_row(sequence=15, timestamp_ms=1500),
        make_row(sequence=25, timestamp_ms=2500),
    ]

    _, coverage = runner.build_verification_evidence(
        connection,
        SESSION_ID,
        rows,
    )

    assert coverage.checkpoint_count == 2
    assert coverage.covered_count == 1
    assert coverage.uncovered_count == 1
    assert coverage.all_checkpoints_covered is False
    assert coverage.checkpoints[1].covered is False
    assert coverage.checkpoints[1].initial_snapshot_id is None
    assert coverage.checkpoints[1].final_snapshot_id is None


def test_empty_rows_still_run_snapshot_verification(
    connection,
    monkeypatch,
):
    report = make_report("matched")
    calls = patch_verifier(monkeypatch, report)

    verification, coverage = (
        runner.build_verification_evidence(
            connection,
            SESSION_ID,
            [],
        )
    )

    assert calls == [SESSION_ID]
    assert verification is report
    assert coverage is None


def test_zero_matched_pairs_produce_zero_coverage(
    connection,
    monkeypatch,
):
    empty_report = SessionVerificationReport(
        session_id=SESSION_ID,
        snapshot_count=1,
        token_count=1,
        eligible_pair_count=0,
        matched_pair_count=0,
        mismatched_pair_count=0,
        error_count=0,
        results=(),
    )

    patch_verifier(monkeypatch, empty_report)

    _, coverage = runner.build_verification_evidence(
        connection,
        SESSION_ID,
        [make_row()],
    )

    assert coverage.checkpoint_count == 1
    assert coverage.covered_count == 0
    assert coverage.uncovered_count == 1


def test_verification_errors_remain_visible(
    connection,
    monkeypatch,
    capsys,
):
    pair = PairResult(
        initial_snapshot_id=1,
        final_snapshot_id=2,
        token_id=TOKEN_ID,
        session_id=SESSION_ID,
        status="invalid_sequence",
        updates_applied=None,
        error="Missing or non-increasing sequence",
    )

    report = SessionVerificationReport(
        session_id=SESSION_ID,
        snapshot_count=2,
        token_count=1,
        eligible_pair_count=1,
        matched_pair_count=0,
        mismatched_pair_count=0,
        error_count=1,
        results=(pair,),
    )

    patch_verifier(monkeypatch, report)

    verification, coverage = (
        runner.build_verification_evidence(
            connection,
            SESSION_ID,
            [make_row()],
        )
    )

    runner.print_snapshot_pair_report(verification)

    output = capsys.readouterr().out

    assert "Errors: 1" in output
    assert "STATUS=invalid_sequence" in output
    assert "Missing or non-increasing sequence" in output
    assert coverage.covered_count == 0


def test_snapshot_pair_report_prints_matched_counts(capsys):
    runner.print_snapshot_pair_report(
        make_report("matched"),
    )

    output = capsys.readouterr().out

    assert "SNAPSHOT-PAIR VERIFICATION" in output
    assert "Candidate pairs: 1" in output
    assert "Matched: 1" in output
    assert "Mismatched: 0" in output
    assert "Errors: 0" in output
    assert "PAIR=1->2" in output
