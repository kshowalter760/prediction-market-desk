
import argparse
import sqlite3
from pathlib import Path


EVENT_TABLES = (
    "order_book_snapshots",
    "market_level_updates",
    "market_price_changes",
)


def column_names(connection, table):
    return {
        row[1]
        for row in connection.execute(
            f"PRAGMA table_info({table})"
        )
    }


def migrate(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS polymarket_stream_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at_utc TEXT NOT NULL,
            ended_at_utc TEXT,
            disconnect_reason TEXT,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (
                    status IN (
                        'active',
                        'completed',
                        'disconnected',
                        'failed'
                    )
                )
        )
        """
    )

    for table in EVENT_TABLES:
        existing = column_names(connection, table)

        if "stream_session_id" not in existing:
            connection.execute(
                f"""
                ALTER TABLE {table}
                ADD COLUMN stream_session_id INTEGER
                REFERENCES polymarket_stream_sessions(id)
                """
            )

        if "message_sequence" not in existing:
            connection.execute(
                f"""
                ALTER TABLE {table}
                ADD COLUMN message_sequence INTEGER
                """
            )

        connection.execute(
            f"""
            CREATE INDEX IF NOT EXISTS
                idx_{table}_stream_order
            ON {table} (
                stream_session_id,
                message_sequence,
                id
            )
            """
        )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--database",
        default="data/prediction_markets.db",
    )

    args = parser.parse_args()
    database = Path(args.database)

    if not database.is_file():
        raise FileNotFoundError(
            f"Database not found: {database.resolve()}"
        )

    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            migrate(connection)

        print("Polymarket session migration complete.")

        for table in EVENT_TABLES:
            print(
                table,
                sorted(column_names(connection, table)),
            )


if __name__ == "__main__":
    main()
