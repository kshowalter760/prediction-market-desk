
from pathlib import Path

from prediction_desk.storage import Storage


def main():
    database_path = Path("data/prediction_markets.db")

    with Storage(database_path) as storage:
        if storage.connection.in_transaction:
            raise RuntimeError(
                "Cannot change journal mode inside a transaction"
            )

        row = storage.connection.execute(
            "PRAGMA journal_mode = WAL"
        ).fetchone()

        mode = row[0].lower()

        if mode != "wal":
            raise RuntimeError(
                f"Failed to enable WAL: {mode}"
            )

        print("SQLite journal mode:", mode)

        timeout = storage.connection.execute(
            "PRAGMA busy_timeout"
        ).fetchone()[0]

        print("Busy timeout:", timeout, "ms")

        print(
            "Transaction active:",
            storage.connection.in_transaction,
        )


if __name__ == "__main__":
    main()
