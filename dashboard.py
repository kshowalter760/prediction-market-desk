
from pathlib import Path
import sqlite3

import streamlit as st

from prediction_desk.dashboard_data import read_query, count_rows


PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE = PROJECT_ROOT / "data" / "prediction_markets.db"


st.set_page_config(
    page_title="Prediction Markets Desk",
    page_icon="📊",
    layout="wide",
)


st.title("Prediction Markets Desk")
st.caption(
    "Research dashboard | Historical observations | v0.1.0"
)


if not DATABASE.is_file():
    st.error(f"Research database not found: {DATABASE}")
    st.stop()


try:
    # ---------------------------------------------------------
    # Market registry
    # ---------------------------------------------------------

    markets = read_query(
        DATABASE,
        """
        SELECT
            market_id,
            event_title,
            question,
            asset,
            market_type,
            end_date
        FROM markets
        ORDER BY end_date DESC
        """,
    )

    # ---------------------------------------------------------
    # Historical order book observations
    # ---------------------------------------------------------

    snapshots = read_query(
        DATABASE,
        """
        SELECT
            s.token_id,
            m.asset,
            m.question,
            o.outcome_name,
            s.observed_at_utc,
            s.best_bid,
            s.best_ask,
            s.spread
        FROM order_book_snapshots AS s
        LEFT JOIN outcomes AS o
            ON s.token_id = o.token_id
        LEFT JOIN markets AS m
            ON o.market_id = m.market_id
        ORDER BY s.id DESC
        LIMIT 100
        """,
    )

    # ---------------------------------------------------------
    # Polymarket collection sessions
    # ---------------------------------------------------------

    polymarket_sessions = read_query(
        DATABASE,
        """
        SELECT
            id,
            started_at_utc,
            ended_at_utc,
            status,
            disconnect_reason
        FROM polymarket_stream_sessions
        ORDER BY id DESC
        LIMIT 20
        """,
    )

    # ---------------------------------------------------------
    # Coinbase collection sessions
    # ---------------------------------------------------------

    spot_sessions = read_query(
        DATABASE,
        """
        SELECT
            id,
            started_at_utc,
            completed_at_utc,
            status,
            termination_reason
        FROM spot_stream_sessions
        ORDER BY id DESC
        LIMIT 20
        """,
    )

    # ---------------------------------------------------------
    # Summary metrics
    # ---------------------------------------------------------

    market_count = count_rows(DATABASE, "markets")

    outcome_count = count_rows(DATABASE, "outcomes")

    snapshot_count = count_rows(
        DATABASE,
        "order_book_snapshots",
    )

    spot_trade_count = count_rows(
        DATABASE,
        "spot_trades",
    )

except (sqlite3.Error, ValueError, FileNotFoundError) as exc:
    st.error(f"Unable to load research data: {exc}")
    st.stop()


# -------------------------------------------------------------
# Dashboard summary
# -------------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Registered Markets",
    f"{market_count:,}",
)

col2.metric(
    "Registered Outcomes",
    f"{outcome_count:,}",
)

col3.metric(
    "Book Snapshots",
    f"{snapshot_count:,}",
)

col4.metric(
    "Spot Trades",
    f"{spot_trade_count:,}",
)

st.divider()


# -------------------------------------------------------------
# Dashboard navigation
# -------------------------------------------------------------

market_tab, book_tab, health_tab = st.tabs(
    [
        "Market Explorer",
        "Order Book History",
        "Collection Health",
    ]
)


# -------------------------------------------------------------
# Market Explorer
# -------------------------------------------------------------

with market_tab:

    st.subheader("Registered Prediction Markets")

    if markets.empty:
        st.info("No registered markets found.")

    else:
        assets = sorted(
            markets["asset"].dropna().unique().tolist()
        )

        selected_assets = st.multiselect(
            "Filter by asset",
            options=assets,
            default=assets,
        )

        filtered_markets = markets[
            markets["asset"].isin(selected_assets)
        ]

        st.dataframe(
            filtered_markets,
            width="stretch",
            hide_index=True,
        )


# -------------------------------------------------------------
# Order Book History
# -------------------------------------------------------------

with book_tab:

    st.subheader(
        "Recent Historical Order Book Snapshots"
    )

    st.caption(
        "The latest 100 stored snapshots, ordered by "
        "database insertion ID. These are not live quotes."
    )

    if snapshots.empty:
        st.info(
            "No order book snapshots available."
        )

    else:
        st.dataframe(
            snapshots,
            width="stretch",
            hide_index=True,
        )


# -------------------------------------------------------------
# Collection Health
# -------------------------------------------------------------

with health_tab:

    st.subheader("Collection Session History")

    st.markdown(
        "**Polymarket Stream Sessions**"
    )

    if polymarket_sessions.empty:
        st.info(
            "No Polymarket stream sessions recorded."
        )

    else:
        st.dataframe(
            polymarket_sessions,
            width="stretch",
            hide_index=True,
        )

    st.markdown(
        "**Coinbase Spot Stream Sessions**"
    )

    if spot_sessions.empty:
        st.info(
            "No spot stream sessions recorded."
        )

    else:
        st.dataframe(
            spot_sessions,
            width="stretch",
            hide_index=True,
        )


# -------------------------------------------------------------
# Research disclaimer
# -------------------------------------------------------------

st.divider()

st.caption(
    "Exploratory research only. Stored observations are not "
    "independently verified trading signals."
)
