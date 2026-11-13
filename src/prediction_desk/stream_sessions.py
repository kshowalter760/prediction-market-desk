
from dataclasses import dataclass
from datetime import datetime, timezone


VALID_FINAL_STATUSES = {
    "completed",
    "disconnected",
    "failed",
}


@dataclass(frozen=True)
class StreamSession:
    session_id: int
    started_at_utc: str
    ended_at_utc: str | None
    status: str
    disconnect_reason: str | None


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def start_stream_session(connection):
    started_at = utc_now()

    with connection:
        cursor = connection.execute(
            """
            INSERT INTO polymarket_stream_sessions (
                started_at_utc,
                status
            )
            VALUES (?, 'active')
            """,
            (started_at,),
        )

    return cursor.lastrowid


def finish_stream_session(
    connection,
    session_id,
    *,
    status,
    disconnect_reason=None,
):
    if status not in VALID_FINAL_STATUSES:
        raise ValueError("Invalid final session status")

    if type(session_id) is not int or session_id <= 0:
        raise ValueError("Invalid session ID")

    with connection:
        cursor = connection.execute(
            """
            UPDATE polymarket_stream_sessions
            SET
                ended_at_utc = ?,
                status = ?,
                disconnect_reason = ?
            WHERE id = ?
              AND status = 'active'
            """,
            (
                utc_now(),
                status,
                disconnect_reason,
                session_id,
            ),
        )

        if cursor.rowcount != 1:
            raise ValueError(
                "Session not found or already finished"
            )


def get_stream_session(connection, session_id):
    row = connection.execute(
        """
        SELECT
            id,
            started_at_utc,
            ended_at_utc,
            status,
            disconnect_reason
        FROM polymarket_stream_sessions
        WHERE id = ?
        """,
        (session_id,),
    ).fetchone()

    if row is None:
        raise ValueError("Session not found")

    return StreamSession(*row)
