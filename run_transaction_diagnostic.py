
from pathlib import Path

from prediction_desk.storage import Storage
from prediction_desk.stream_sessions import (
    start_stream_session,
    finish_stream_session,
)


def main():
    database_path = Path("data/transaction_diagnostic.db")

    with Storage(database_path) as storage:
        print(
            "After connection:",
            storage.connection.in_transaction,
        )

        storage.initialize()

        print(
            "After initialize:",
            storage.connection.in_transaction,
        )

        session_id = start_stream_session(
            storage.connection
        )

        print(
            "After start_stream_session:",
            storage.connection.in_transaction,
        )

        print("Session ID:", session_id)

        finish_stream_session(
            storage.connection,
            session_id,
            status="completed",
        )

        print(
            "After finish_stream_session:",
            storage.connection.in_transaction,
        )


if __name__ == "__main__":
    main()
