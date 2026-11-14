
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


def load_price_history(
    database: Path,
    token_id: str,
    limit: int = 1000,
) -> pd.DataFrame:
    """Load historical bid/ask observations for one outcome token.

    Observations are ordered by their recorded timestamps.
    Missing quotes remain missing; no interpolation is applied.
    """

    if not isinstance(token_id, str) or not token_id.strip():
        raise ValueError("token_id must be a non-empty string")

    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit <= 0
    ):
        raise ValueError("limit must be a positive integer")

    query = """
        SELECT
            observed_at_utc,
            best_bid,
            best_ask,
            spread
        FROM (
            SELECT
                id,
                observed_at_utc,
                best_bid,
                best_ask,
                spread
            FROM order_book_snapshots
            WHERE token_id = ?
            ORDER BY id DESC
            LIMIT ?
        )
        ORDER BY id ASC
    """

    result = read_query(
        database,
        query,
        (token_id, limit),
    )

    if result.empty:
        return result

    result["observed_at_utc"] = pd.to_datetime(
        result["observed_at_utc"],
        utc=True,
        errors="coerce",
    )

    for column in ("best_bid", "best_ask", "spread"):
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    return result


def summarize_price_history(
    history: pd.DataFrame,
) -> dict:
    """Summarize observation coverage and missing quote data."""

    required_columns = {
        "observed_at_utc",
        "best_bid",
        "best_ask",
    }

    missing_columns = required_columns - set(history.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    total_observations = len(history)

    timestamps = pd.to_datetime(
        history["observed_at_utc"],
        utc=True,
        errors="coerce",
    )

    valid_timestamps = timestamps.dropna().sort_values()

    bid = pd.to_numeric(history["best_bid"], errors="coerce")
    ask = pd.to_numeric(history["best_ask"], errors="coerce")

    missing_bid_count = int(bid.isna().sum())
    missing_ask_count = int(ask.isna().sum())

    if valid_timestamps.empty:
        first_observation = None
        last_observation = None
        duration_seconds = None
        largest_gap_seconds = None

    else:
        first_observation = valid_timestamps.iloc[0]
        last_observation = valid_timestamps.iloc[-1]

        duration_seconds = (
            last_observation - first_observation
        ).total_seconds()

        gaps = valid_timestamps.diff().dropna()

        largest_gap_seconds = (
            gaps.max().total_seconds()
            if not gaps.empty
            else None
        )

    return {
        "total_observations": total_observations,
        "first_observation": first_observation,
        "last_observation": last_observation,
        "duration_seconds": duration_seconds,
        "largest_gap_seconds": largest_gap_seconds,
        "missing_bid_count": missing_bid_count,
        "missing_ask_count": missing_ask_count,
    }


def prepare_market_options(
    tokens: pd.DataFrame,
) -> pd.DataFrame:
    """Prepare unique, readable market selections.

    The full token ID is preserved for database queries.
    Missing registry metadata is labeled explicitly.
    """

    required_columns = {
        "token_id",
        "asset",
        "question",
        "outcome_name",
    }

    missing_columns = required_columns - set(tokens.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    result = tokens.copy()

    # Remove invalid token identifiers.
    result = result.dropna(subset=["token_id"])

    result["token_id"] = (
        result["token_id"].astype(str).str.strip()
    )

    result = result[
        result["token_id"] != ""
    ].copy()

    if result.empty:
        result["display_name"] = pd.Series(dtype=str)
        result["registry_status"] = pd.Series(dtype=str)
        return result

    # Prefer rows containing more registry information
    # when multiple rows reference the same token.
    metadata_columns = [
        "asset",
        "question",
        "outcome_name",
    ]

    result["_metadata_count"] = (
        result[metadata_columns].notna().sum(axis=1)
    )

    result = result.sort_values(
        "_metadata_count",
        ascending=False,
        kind="stable",
    )

    result = result.drop_duplicates(
        subset=["token_id"],
        keep="first",
    ).copy()

    # Registry status is based on whether the token has
    # a matching market/outcome relationship.
    if "market_id" in result.columns:
        result["registry_status"] = result[
            "market_id"
        ].apply(
            lambda value: (
                "Registered"
                if pd.notna(value)
                else "Unregistered"
            )
        )
    else:
        result["registry_status"] = "Unknown"

    def clean_label(value, fallback):
        if pd.isna(value):
            return fallback

        cleaned = str(value).strip()

        return cleaned if cleaned else fallback

    def build_label(row):
        asset = clean_label(
            row["asset"],
            "Unknown asset",
        )

        question = clean_label(
            row["question"],
            "Unregistered market",
        )

        outcome = clean_label(
            row["outcome_name"],
            "Unknown outcome",
        )

        token_id = row["token_id"]

        short_token = (
            token_id[:8] + "..." + token_id[-6:]
            if len(token_id) > 20
            else token_id
        )

        return (
            f"{asset} | {question} | {outcome} "
            f"| {row['registry_status']} "
            f"| {short_token}"
        )

    result["display_name"] = result.apply(
        build_label,
        axis=1,
    )

    result = result.drop(
        columns=["_metadata_count"]
    )

    return result.reset_index(drop=True)



def load_order_book_depth(
    database: Path,
    snapshot_id: int,
) -> pd.DataFrame:
    """Load and validate historical order-book depth.

    BUY levels are sorted from highest to lowest price.
    SELL levels are sorted from lowest to highest price.

    Cumulative quantities are calculated independently
    for each side of the book.

    Missing book sides are not reconstructed.
    """

    if (
        isinstance(snapshot_id, bool)
        or not isinstance(snapshot_id, int)
        or snapshot_id <= 0
    ):
        raise ValueError(
            "snapshot_id must be a positive integer"
        )

    levels = read_query(
        database,
        """
        SELECT
            side,
            price,
            size
        FROM order_book_levels
        WHERE snapshot_id = ?
        """,
        (snapshot_id,),
    )

    columns = [
        "side",
        "price",
        "size",
        "cumulative_size",
    ]

    if levels.empty:
        return pd.DataFrame(columns=columns)

    result = levels.copy()

    result["side"] = (
        result["side"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    result["price"] = pd.to_numeric(
        result["price"],
        errors="coerce",
    )

    result["size"] = pd.to_numeric(
        result["size"],
        errors="coerce",
    )

    # ---------------------------------------------------------
    # Numeric and structural validation
    # ---------------------------------------------------------

    import numpy as np

    valid = (
        result["side"].isin(["BUY", "SELL"])
        & np.isfinite(result["price"])
        & result["price"].between(0, 1)
        & np.isfinite(result["size"])
        & (result["size"] > 0)
    )

    if not valid.all():
        raise ValueError(
            f"Snapshot {snapshot_id} contains invalid "
            "order-book levels"
        )

    # A single snapshot must not contain multiple
    # entries for the same side and price.
    duplicates = result.duplicated(
        subset=["side", "price"],
        keep=False,
    )

    if duplicates.any():
        raise ValueError(
            f"Snapshot {snapshot_id} contains "
            "duplicate price levels"
        )

    # ---------------------------------------------------------
    # Separate and sort book sides
    # ---------------------------------------------------------

    bids = result[
        result["side"] == "BUY"
    ].sort_values(
        "price",
        ascending=False,
    ).copy()

    asks = result[
        result["side"] == "SELL"
    ].sort_values(
        "price",
        ascending=True,
    ).copy()

    # ---------------------------------------------------------
    # Crossed-book validation
    # ---------------------------------------------------------

    if not bids.empty and not asks.empty:

        best_bid = bids.iloc[0]["price"]
        best_ask = asks.iloc[0]["price"]

        if best_bid > best_ask:
            raise ValueError(
                f"Snapshot {snapshot_id} contains "
                "a crossed order book"
            )

    # ---------------------------------------------------------
    # Cumulative quoted contract quantities
    # ---------------------------------------------------------

    bids["cumulative_size"] = (
        bids["size"].cumsum()
    )

    asks["cumulative_size"] = (
        asks["size"].cumsum()
    )

    return pd.concat(
        [bids, asks],
        ignore_index=True,
    )[columns]




def load_depth_snapshots(
    database: Path,
) -> pd.DataFrame:
    """Return snapshots containing recorded order-book levels."""

    return read_query(
        database,
        """
        SELECT
            s.id AS snapshot_id,
            s.token_id,
            s.observed_at_utc,
            m.asset,
            m.question,
            o.outcome_name,
            COUNT(l.id) AS level_count
        FROM order_book_snapshots AS s
        JOIN order_book_levels AS l
            ON l.snapshot_id = s.id
        LEFT JOIN outcomes AS o
            ON s.token_id = o.token_id
        LEFT JOIN markets AS m
            ON o.market_id = m.market_id
        GROUP BY
            s.id,
            s.token_id,
            s.observed_at_utc,
            m.asset,
            m.question,
            o.outcome_name
        ORDER BY s.id DESC
        """,
    )