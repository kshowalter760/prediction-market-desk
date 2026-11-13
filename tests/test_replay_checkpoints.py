
import pytest

from prediction_desk.replay_checkpoints import (
    reconstruct_checkpoints,
)

from test_replay_integrity_end_to_end import (
    db,
    seed_atomic_transition,
    insert_update,
)


def test_atomic_transition_checkpoint(db):
    seed_atomic_transition(db)

    checkpoints = reconstruct_checkpoints(
        db,
        snapshot_id=1,
        interval_ms=100,
    )

    assert len(checkpoints) == 1

    checkpoint = checkpoints[0]

    assert checkpoint.message_sequence == 3
    assert checkpoint.timestamp_ms == 1100
    assert checkpoint.updates_applied == 2
    assert str(checkpoint.book.best_bid) == "0.001"
    assert str(checkpoint.book.best_ask) == "0.01"


def test_no_checkpoint_before_interval(db):
    seed_atomic_transition(db)

    checkpoints = reconstruct_checkpoints(
        db,
        snapshot_id=1,
        interval_ms=200,
    )

    assert checkpoints == []


def test_invalid_interval_rejected(db):
    seed_atomic_transition(db)

    with pytest.raises(
        ValueError,
        match="interval_ms must be positive",
    ):
        reconstruct_checkpoints(
            db,
            snapshot_id=1,
            interval_ms=0,
        )


def test_other_session_updates_excluded(db):
    seed_atomic_transition(db)

    insert_update(
        db,
        update_id=3,
        session_id=99,
        sequence=2,
        timestamp=1100,
        side="SELL",
        price="0.02",
        size="999",
    )

    checkpoints = reconstruct_checkpoints(
        db,
        snapshot_id=1,
        interval_ms=100,
    )

    assert len(checkpoints) == 1
    assert checkpoints[0].updates_applied == 2


def test_corrupt_atomic_batch_rejected(db):
    seed_atomic_transition(db)

    db.execute(
        """
        DELETE FROM market_level_updates
        WHERE id = 2
        """
    )

    with pytest.raises(
        ValueError,
        match="Locked or crossed",
    ):
        reconstruct_checkpoints(
            db,
            snapshot_id=1,
            interval_ms=100,
        )
