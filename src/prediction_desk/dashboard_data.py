
from pathlib import Path
import sqlite3

import pandas as pd


def read_query(
    database: Path,
    query: str,
    params: tuple = (),
) -> pd.DataFrame:
    """Read a SQL query from an existing SQLite database."""

    database = Path(database)

    if not database.is_file():
        raise FileNotFoundError(
            f"Research database not found: {database}"
        )

    uri = database.resolve().as_uri() + "?mode=ro"

    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute("PRAGMA query_only = ON")
        return pd.read_sql_query(
            query,
            connection,
            params=params,
        )


def count_rows(database: Path, table: str) -> int:
    """Count rows in a supported dashboard table."""

    allowed_tables = {
        "markets",
        "outcomes",
        "order_book_snapshots",
        "spot_trades",
    }

    if table not in allowed_tables:
        raise ValueError(f"Unsupported table: {table}")

    result = read_query(
        database,
        f'SELECT COUNT(*) AS count FROM "{table}"',
    )

    return int(result.iloc[0]["count"])
