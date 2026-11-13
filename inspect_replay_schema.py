
import sqlite3

DATABASE = "data/prediction_markets.db"

connection = sqlite3.connect(
    f"file:{DATABASE}?mode=ro",
    uri=True,
)

try:
    tables = (
        "order_book_snapshots",
        "market_level_updates",
        "stream_sessions",
    )

    for table in tables:
        print()
        print("=" * 75)
        print("TABLE:", table)
        print("=" * 75)

        columns = connection.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()

        if not columns:
            print("Table not found")
            continue

        for column in columns:
            print(
                f"{column[1]:30} "
                f"{column[2]:15} "
                f"NOT NULL={bool(column[3])}"
            )

    print()
    print("=" * 75)
    print("SESSION 5 SNAPSHOTS")
    print("=" * 75)

    rows = connection.execute(
        """
        SELECT
            id,
            token_id,
            stream_session_id,
            message_sequence,
            source_timestamp_ms
        FROM order_book_snapshots
        WHERE stream_session_id = ?
        ORDER BY token_id, message_sequence, id
        """,
        (5,),
    ).fetchall()

    for row in rows:
        snapshot_id, token_id, session_id, sequence, timestamp = row

        print(
            f"ID={snapshot_id} "
            f"TOKEN={token_id[:16]}... "
            f"SESSION={session_id} "
            f"SEQUENCE={sequence} "
            f"TIME={timestamp}"
        )

    print()
    print("Total session 5 snapshots:", len(rows))

finally:
    connection.close()
