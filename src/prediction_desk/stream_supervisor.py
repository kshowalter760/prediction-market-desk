
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

from prediction_desk.spot_stream import (
    COINBASE_WS_URL,
    build_subscription,
    process_trade_messages,
)
from prediction_desk.stream_audit import (
    assess_stream_continuity,
)


@dataclass(frozen=True)
class SupervisedStreamResult:
    session_id: int
    status: str
    termination_reason: str
    connection_attempts: int
    messages_received: int
    trades_received: int
    trades_inserted: int
    ignored_messages: int
    potential_id_gaps: int


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def run_supervised_stream(
    storage,
    max_messages=100,
    max_attempts=3,
    receive_timeout_seconds=10,
    backoff_seconds=1.0,
    connect_fn=connect,
    sleep_fn=time.sleep,
    duration_seconds=None,
    monotonic_fn=time.monotonic,
):
    # Validate message limit.
    if (
        type(max_messages) is not int
        or max_messages <= 0
    ):
        raise ValueError(
            "max_messages must be positive"
        )

    # Validate connection attempts.
    if (
        type(max_attempts) is not int
        or max_attempts <= 0
    ):
        raise ValueError(
            "max_attempts must be positive"
        )

    # Validate reconnection backoff.
    if (
        isinstance(backoff_seconds, bool)
        or not isinstance(
            backoff_seconds, (int, float)
        )
        or not 0 <= backoff_seconds < float("inf")
    ):
        raise ValueError("Invalid backoff")

    # Validate receive timeout.
    if (
        isinstance(receive_timeout_seconds, bool)
        or not isinstance(
            receive_timeout_seconds, (int, float)
        )
        or not 0 < receive_timeout_seconds < float("inf")
    ):
        raise ValueError(
            "Invalid receive timeout"
        )

    # Validate optional session duration.
    if duration_seconds is not None:
        if (
            isinstance(duration_seconds, bool)
            or not isinstance(
                duration_seconds, (int, float)
            )
            or not 0 < duration_seconds < float("inf")
        ):
            raise ValueError(
                "Invalid duration"
            )

    deadline = (
        monotonic_fn() + duration_seconds
        if duration_seconds is not None
        else None
    )

    # Start an auditable SQLite session.
    session_id = storage.start_spot_stream_session(
        utc_now()
    )

    attempts = 0
    messages_received = 0
    trades_received = 0
    trades_inserted = 0
    ignored_messages = 0

    received_trades = []

    status = "failed"
    termination_reason = "attempts_exhausted"

    try:
        while (
            attempts < max_attempts
            and messages_received < max_messages
            and (
                deadline is None
                or monotonic_fn() < deadline
            )
        ):
            attempts += 1

            try:
                with connect_fn(
                    COINBASE_WS_URL,
                    open_timeout=15,
                    close_timeout=5,
                ) as websocket:
                    websocket.send(
                        json.dumps(
                            build_subscription()
                        )
                    )

                    while messages_received < max_messages:
                        # Calculate remaining session time.
                        if deadline is not None:
                            remaining = (
                                deadline - monotonic_fn()
                            )

                            if remaining <= 0:
                                status = "completed"
                                termination_reason = (
                                    "duration_limit"
                                )
                                break

                            timeout = min(
                                receive_timeout_seconds,
                                remaining,
                            )
                        else:
                            timeout = receive_timeout_seconds

                        try:
                            raw_message = websocket.recv(
                                timeout=timeout
                            )

                        except TimeoutError:
                            status = "completed"

                            if (
                                deadline is not None
                                and monotonic_fn() >= deadline
                            ):
                                termination_reason = (
                                    "duration_limit"
                                )
                            else:
                                termination_reason = (
                                    "receive_timeout"
                                )

                            break

                        result = process_trade_messages(
                            [raw_message],
                            storage,
                            max_messages=1,
                            on_trade=received_trades.append,
                        )

                        messages_received += (
                            result.messages_received
                        )

                        trades_received += (
                            result.trades_received
                        )

                        trades_inserted += (
                            result.trades_inserted
                        )

                        ignored_messages += (
                            result.ignored_messages
                        )

                    # Stop when message limit is reached.
                    if messages_received >= max_messages:
                        status = "completed"
                        termination_reason = (
                            "message_limit"
                        )

                    if status == "completed":
                        break

            except (
                ConnectionClosed,
                ConnectionError,
                OSError,
            ):
                # Reconnect unless attempts are exhausted.
                if attempts >= max_attempts:
                    termination_reason = (
                        "attempts_exhausted"
                    )
                    break

                # Avoid sleeping beyond the session deadline.
                delay = (
                    backoff_seconds
                    * (2 ** (attempts - 1))
                )

                if deadline is not None:
                    remaining = (
                        deadline - monotonic_fn()
                    )

                    if remaining <= 0:
                        status = "completed"
                        termination_reason = (
                            "duration_limit"
                        )
                        break

                    delay = min(delay, remaining)

                sleep_fn(delay)

        # Handle duration expiration between attempts.
        if (
            status != "completed"
            and deadline is not None
            and monotonic_fn() >= deadline
        ):
            status = "completed"
            termination_reason = "duration_limit"

        elif status != "completed":
            termination_reason = (
                "attempts_exhausted"
            )

    except KeyboardInterrupt:
        status = "interrupted"
        termination_reason = (
            "keyboard_interrupt"
        )

    except Exception as exc:
        status = "failed"
        termination_reason = type(exc).__name__
        raise

    finally:
        # Audit Coinbase trade-ID continuity.
        audit = assess_stream_continuity(
            received_trades
        )

        # Always finalize the database session.
        storage.finish_spot_stream_session(
            session_id=session_id,
            completed_at_utc=utc_now(),
            status=status,
            termination_reason=termination_reason,
            connection_attempts=attempts,
            messages_received=messages_received,
            trades_received=trades_received,
            trades_inserted=trades_inserted,
            ignored_messages=ignored_messages,
            potential_id_gaps=audit.total_potential_gaps,
        )

    return SupervisedStreamResult(
        session_id=session_id,
        status=status,
        termination_reason=termination_reason,
        connection_attempts=attempts,
        messages_received=messages_received,
        trades_received=trades_received,
        trades_inserted=trades_inserted,
        ignored_messages=ignored_messages,
        potential_id_gaps=audit.total_potential_gaps,
    )
