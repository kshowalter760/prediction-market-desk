
import sqlite3
from pathlib import Path


DATABASE = Path("data/prediction_markets.db")


def audit_latest_stream_session(connection):
    print()
    print("LATEST STREAM SESSION REPLAY COVERAGE")
    print("=" * 65)

    session = connection.execute(
        """
        SELECT
            id,
            started_at_utc,
            ended_at_utc,
            status
        FROM polymarket_stream_sessions
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    if session is None:
        print("No Polymarket stream sessions found.")
        return

    session_id = session["id"]

    print("Session ID:", session_id)
    print("Started:", session["started_at_utc"])
    print("Ended:", session["ended_at_utc"])
    print("Status:", session["status"])

    snapshots = connection.execute(
        """
        SELECT
            s.id,
            s.token_id,
            s.message_sequence,
            s.source_timestamp_ms,
            COUNT(l.id) AS depth_levels
        FROM order_book_snapshots AS s
        LEFT JOIN order_book_levels AS l
            ON l.snapshot_id = s.id
        WHERE s.stream_session_id = ?
        GROUP BY
            s.id,
            s.token_id,
            s.message_sequence,
            s.source_timestamp_ms
        ORDER BY s.message_sequence, s.id
        """,
        (session_id,),
    ).fetchall()

    print()
    print("FULL-DEPTH SNAPSHOTS")

    for row in snapshots:
        print(
            f"Snapshot {row['id']} | "
            f"Token {row['token_id'][:16]}... | "
            f"Sequence {row['message_sequence']} | "
            f"Levels {row['depth_levels']}"
        )

    if not snapshots:
        print("No snapshots found for this session.")

    updates = connection.execute(
        """
        SELECT
            token_id,
            COUNT(*) AS update_count,
            MIN(message_sequence) AS first_sequence,
            MAX(message_sequence) AS last_sequence
        FROM market_level_updates
        WHERE stream_session_id = ?
        GROUP BY token_id
        ORDER BY token_id
        """,
        (session_id,),
    ).fetchall()

    print()
    print("INCREMENTAL LEVEL UPDATES")

    for row in updates:
        print(
            f"Token {row['token_id'][:16]}... | "
            f"Updates {row['update_count']} | "
            f"Sequence range "
            f"{row['first_sequence']}–{row['last_sequence']}"
        )

    if not updates:
        print("No level updates found for this session.")

    print()
    print("REPLAY WINDOWS")

    windows = connection.execute(
        """
        SELECT
            s.id AS snapshot_id,
            s.token_id,
            s.message_sequence AS start_sequence,
            (
                SELECT MIN(next_s.message_sequence)
                FROM order_book_snapshots AS next_s
                WHERE next_s.stream_session_id =
                    s.stream_session_id
                  AND next_s.token_id = s.token_id
                  AND next_s.message_sequence >
                    s.message_sequence
            ) AS next_snapshot_sequence
        FROM order_book_snapshots AS s
        WHERE s.stream_session_id = ?
        ORDER BY s.message_sequence, s.id
        """,
        (session_id,),
    ).fetchall()

    found_window = False

    for window in windows:
        next_sequence = window["next_snapshot_sequence"]

        if next_sequence is None:
            continue

        found_window = True

        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM market_level_updates
            WHERE stream_session_id = ?
              AND token_id = ?
              AND message_sequence > ?
              AND message_sequence < ?
            """,
            (
                session_id,
                window["token_id"],
                window["start_sequence"],
                next_sequence,
            ),
        ).fetchone()[0]

        print(
            f"Snapshot {window['snapshot_id']} | "
            f"Token {window['token_id'][:16]}... | "
            f"Sequence "
            f"{window['start_sequence']} → {next_sequence} | "
            f"Updates {count}"
        )

    if not found_window:
        print("No consecutive snapshot windows found.")


def main():
    if not DATABASE.is_file():
        raise FileNotFoundError(DATABASE)

    with sqlite3.connect(DATABASE) as connection:
        connection.row_factory = sqlite3.Row

        print("DATABASE TABLES")
        print("=" * 65)

        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        for table in tables:
            print(table["name"])

        print()
        print("EVENT STORAGE SCHEMA")
        print("=" * 65)

        for table_name in (
            "order_book_snapshots",
            "market_level_updates",
            "market_price_changes",
        ):
            print(f"\n{table_name}")

            columns = connection.execute(
                f"PRAGMA table_info({table_name})"
            ).fetchall()

            for column in columns:
                print(
                    f"  {column['name']}: "
                    f"{column['type']}"
                )

        print()
        print("RECENT SNAPSHOT COVERAGE")
        print("=" * 65)

        snapshots = connection.execute(
            """
            SELECT
                id,
                substr(token_id, 1, 18) AS token,
                source_timestamp_ms,
                observed_at_utc
            FROM order_book_snapshots
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()

        for row in snapshots:
            print(dict(row))

        print()
        print("LEVEL UPDATE COVERAGE")
        print("=" * 65)

        coverage = connection.execute(
            """
            SELECT
                substr(token_id, 1, 18) AS token,
                COUNT(*) AS updates,
                MIN(source_timestamp_ms) AS first_ms,
                MAX(source_timestamp_ms) AS last_ms
            FROM market_level_updates
            GROUP BY token_id
            ORDER BY updates DESC
            LIMIT 10
            """
        ).fetchall()

        for row in coverage:
            print(dict(row))

        print()
        print("EVENT TIMESTAMP ANOMALIES")
        print("=" * 65)

        for table_name in (
            "market_level_updates",
            "market_price_changes",
        ):
            result = connection.execute(
                f"""
                SELECT
                    COUNT(*) AS total,
                    SUM(
                        CASE
                            WHEN source_timestamp_ms IS NULL
                            THEN 1 ELSE 0
                        END
                    ) AS missing_timestamps
                FROM {table_name}
                """
            ).fetchone()

            print(table_name, dict(result))

        # New session-aware replay coverage audit.
        audit_latest_stream_session(connection)


if __name__ == "__main__":
    main()

