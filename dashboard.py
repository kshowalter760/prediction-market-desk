
from pathlib import Path
import sqlite3

import streamlit as st

from prediction_desk.dashboard_data import (
    read_query,
    count_rows,
    load_price_history,
    summarize_price_history,
    prepare_market_options,
    load_depth_snapshots,
    load_order_book_depth,
)


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


# -------------------------------------------------------------
# Load dashboard data
# -------------------------------------------------------------

try:
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

    market_count = count_rows(DATABASE, "markets")
    outcome_count = count_rows(DATABASE, "outcomes")
    snapshot_count = count_rows(
        DATABASE, "order_book_snapshots"
    )
    spot_trade_count = count_rows(
        DATABASE, "spot_trades"
    )

except (
    sqlite3.Error,
    ValueError,
    FileNotFoundError,
) as exc:
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

market_tab, book_tab, price_tab, depth_tab, health_tab = (
    st.tabs(
        [
            "Market Explorer",
            "Order Book History",
            "Price History",
            "Market Depth",
            "Collection Health",
        ]
    )
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
        st.info("No order book snapshots available.")

    else:
        st.dataframe(
            snapshots,
            width="stretch",
            hide_index=True,
        )


# -------------------------------------------------------------
# Historical Price Visualization
# -------------------------------------------------------------

with price_tab:

    st.subheader("Historical Bid / Ask Prices")

    st.caption(
        "Recorded order-book observations only. "
        "Timestamps represent local collection observations, "
        "not necessarily exchange event times. "
        "Lines connect available observations and do not "
        "establish continuous market coverage."
    )

    try:
        available_tokens = read_query(
            DATABASE,
            """
            SELECT DISTINCT
                s.token_id,
                m.market_id,
                m.asset,
                m.question,
                o.outcome_name
            FROM order_book_snapshots AS s
            LEFT JOIN outcomes AS o
                ON s.token_id = o.token_id
            LEFT JOIN markets AS m
                ON o.market_id = m.market_id
            ORDER BY m.asset, m.question, o.outcome_name
            """,
        )

    except (
        sqlite3.Error,
        ValueError,
        FileNotFoundError,
    ) as exc:
        st.error(
            f"Unable to load chart selections: {exc}"
        )
        available_tokens = None

    if available_tokens is not None:

        if available_tokens.empty:
            st.info(
                "No historical order-book observations "
                "are available for charting."
            )

        else:
            available_tokens = prepare_market_options(
                available_tokens
            )

            selected_index = st.selectbox(
                "Select market and outcome",
                options=available_tokens.index.tolist(),
                format_func=lambda index: (
                    available_tokens.loc[
                        index, "display_name"
                    ]
                ),
            )

            selected_token = str(
                available_tokens.loc[
                    selected_index, "token_id"
                ]
            )

            observation_limit = st.selectbox(
                "Maximum observations",
                options=[100, 500, 1000, 5000],
                index=0,
            )

            try:
                history = load_price_history(
                    DATABASE,
                    selected_token,
                    limit=observation_limit,
                )

            except (
                sqlite3.Error,
                ValueError,
                FileNotFoundError,
            ) as exc:
                st.error(
                    f"Unable to load price history: {exc}"
                )
                history = None

            if history is not None:

                if history.empty:
                    st.info(
                        "No price history found for this token."
                    )

                else:
                    st.metric(
                        "Stored observations loaded",
                        f"{len(history):,}",
                    )

                    # -----------------------------------------
                    # Observation coverage
                    # -----------------------------------------

                    coverage = summarize_price_history(
                        history
                    )

                    st.subheader(
                        "Observation Coverage"
                    )

                    coverage_col1, coverage_col2, coverage_col3 = (
                        st.columns(3)
                    )

                    coverage_col1.metric(
                        "Observations",
                        f"{coverage['total_observations']:,}",
                    )

                    duration = coverage[
                        "duration_seconds"
                    ]

                    coverage_col2.metric(
                        "Observed Time Span",
                        (
                            f"{duration:,.1f} seconds"
                            if duration is not None
                            else "Unavailable"
                        ),
                    )

                    largest_gap = coverage[
                        "largest_gap_seconds"
                    ]

                    coverage_col3.metric(
                        "Largest Timestamp Gap",
                        (
                            f"{largest_gap:,.1f} seconds"
                            if largest_gap is not None
                            else "Unavailable"
                        ),
                    )

                    st.caption(
                        "First observation (UTC): "
                        f"{coverage['first_observation']}"
                    )

                    st.caption(
                        "Last observation (UTC): "
                        f"{coverage['last_observation']}"
                    )

                    missing_bid = coverage[
                        "missing_bid_count"
                    ]
                    missing_ask = coverage[
                        "missing_ask_count"
                    ]

                    if coverage["total_observations"] < 10:
                        st.warning(
                            "Sparse historical data: fewer than "
                            "10 observations are available."
                        )

                    if missing_bid or missing_ask:
                        st.warning(
                            f"Missing quotes: {missing_bid} bid "
                            f"observations and {missing_ask} ask "
                            "observations."
                        )

                    if (
                        largest_gap is not None
                        and largest_gap > 60
                    ):
                        st.warning(
                            "A timestamp gap greater than 60 "
                            "seconds exists between observations. "
                            "This does not independently prove "
                            "that market data was lost."
                        )

                    valid_history = history.dropna(
                        subset=["observed_at_utc"]
                    ).copy()

                    valid_history = (
                        valid_history.sort_values(
                            "observed_at_utc",
                            kind="stable",
                        )
                    )

                    if valid_history.empty:
                        st.warning(
                            "No observations have valid timestamps."
                        )

                    else:
                        # -------------------------------------
                        # Historical bid/ask chart
                        # -------------------------------------

                        chart_data = valid_history[
                            [
                                "observed_at_utc",
                                "best_bid",
                                "best_ask",
                            ]
                        ].set_index("observed_at_utc")

                        if chart_data[
                            ["best_bid", "best_ask"]
                        ].notna().any().any():

                            st.line_chart(
                                chart_data,
                                width="stretch",
                                height=400,
                                y_label="Quoted price",
                                x_label="Observation time (UTC)",
                            )

                        else:
                            st.info(
                                "No valid bid or ask prices "
                                "are available to plot."
                            )

                        # -------------------------------------
                        # Historical spread chart
                        # -------------------------------------

                        spread_data = valid_history[
                            [
                                "observed_at_utc",
                                "spread",
                            ]
                        ].dropna(
                            subset=["spread"]
                        )

                        if not spread_data.empty:

                            st.subheader(
                                "Historical Bid-Ask Spread"
                            )

                            st.caption(
                                "Recorded quoted spreads at "
                                "available observation times. "
                                "Lines between observations do "
                                "not imply continuous market "
                                "coverage."
                            )

                            st.line_chart(
                                spread_data.set_index(
                                    "observed_at_utc"
                                ),
                                width="stretch",
                                height=300,
                                y_label="Quoted spread",
                                x_label="Observation time (UTC)",
                            )

                        else:
                            st.info(
                                "No recorded spread values "
                                "are available for this token."
                            )

                    # -----------------------------------------
                    # Underlying observations
                    # -----------------------------------------

                    st.markdown(
                        "**Underlying Historical Observations**"
                    )

                    st.dataframe(
                        history,
                        width="stretch",
                        hide_index=True,
                    )

                    st.caption(
                        "Missing quotes are retained as missing. "
                        "No forward-filling or interpolation is "
                        "performed by the data-access layer. "
                        "Connecting plotted observations does not "
                        "prove that prices remained unchanged "
                        "between collection times."
                    )


# -------------------------------------------------------------
# Historical Market Depth
# -------------------------------------------------------------

with depth_tab:

    st.subheader("Historical Market Depth")

    st.caption(
        "Recorded order-book levels from a selected "
        "historical snapshot. Quantities are quoted "
        "contract sizes, not USD liquidity. "
        "These are not live executable quotes."
    )

    try:
        depth_snapshots = load_depth_snapshots(
            DATABASE
        )

    except (
        sqlite3.Error,
        ValueError,
        FileNotFoundError,
    ) as exc:
        st.error(
            f"Unable to load depth snapshot selections: {exc}"
        )
        depth_snapshots = None

    if depth_snapshots is not None:

        if depth_snapshots.empty:
            st.info(
                "No snapshots with recorded order-book "
                "depth were found."
            )

        else:
            st.caption(
                f"{len(depth_snapshots):,} snapshots contain "
                f"recorded depth out of {snapshot_count:,} "
                "stored snapshots. Snapshots without depth "
                "records are not reconstructed."
            )

            # -----------------------------------------
            # Build historical snapshot selector
            # -----------------------------------------

            snapshot_options = {}

            for row in depth_snapshots.itertuples(
                index=False
            ):

                snapshot_id = int(
                    row.snapshot_id
                )

                asset = (
                    str(row.asset)
                    if row.asset is not None
                    and str(row.asset) != "nan"
                    else "Unregistered"
                )

                question = (
                    str(row.question)
                    if row.question is not None
                    and str(row.question) != "nan"
                    else (
                        f"Token "
                        f"{str(row.token_id)[:12]}..."
                    )
                )

                outcome = (
                    str(row.outcome_name)
                    if row.outcome_name is not None
                    and str(row.outcome_name) != "nan"
                    else "Unknown outcome"
                )

                snapshot_options[snapshot_id] = (
                    f"#{snapshot_id} | "
                    f"{asset} | "
                    f"{question} | "
                    f"{outcome} | "
                    f"{row.observed_at_utc} UTC"
                )

            selected_snapshot_id = st.selectbox(
                "Select historical snapshot",
                options=list(snapshot_options),
                format_func=lambda snapshot_id: (
                    snapshot_options[snapshot_id]
                ),
                key="historical_depth_snapshot",
            )

            # -----------------------------------------
            # Load validated order-book levels
            # -----------------------------------------

            try:
                depth = load_order_book_depth(
                    DATABASE,
                    int(selected_snapshot_id),
                )

            except (
                sqlite3.Error,
                ValueError,
                FileNotFoundError,
            ) as exc:
                st.error(
                    f"Unable to validate selected snapshot: {exc}"
                )
                depth = None

            if depth is not None:

                if depth.empty:
                    st.warning(
                        "No levels were found for this "
                        "snapshot. Missing depth does not "
                        "mean zero liquidity."
                    )

                else:
                    bids = depth.loc[
                        depth["side"] == "BUY"
                    ].copy()

                    asks = depth.loc[
                        depth["side"] == "SELL"
                    ].copy()

                    best_bid = (
                        float(bids["price"].max())
                        if not bids.empty
                        else None
                    )

                    best_ask = (
                        float(asks["price"].min())
                        if not asks.empty
                        else None
                    )

                    # -----------------------------------------
                    # Depth summary metrics
                    # -----------------------------------------

                    metric_cols = st.columns(4)

                    metric_cols[0].metric(
                        "Recorded bid levels",
                        f"{len(bids):,}",
                    )

                    metric_cols[1].metric(
                        "Recorded ask levels",
                        f"{len(asks):,}",
                    )

                    metric_cols[2].metric(
                        "Best recorded bid",
                        (
                            f"{best_bid:.4f}"
                            if best_bid is not None
                            else "Missing"
                        ),
                    )

                    metric_cols[3].metric(
                        "Best recorded ask",
                        (
                            f"{best_ask:.4f}"
                            if best_ask is not None
                            else "Missing"
                        ),
                    )

                    if bids.empty or asks.empty:
                        st.warning(
                            "One-sided historical book: at "
                            "least one side has no recorded "
                            "levels. Missing is not zero "
                            "liquidity."
                        )

                    # -----------------------------------------
                    # Cumulative depth charts
                    # -----------------------------------------

                    st.subheader(
                        "Cumulative Order-Book Depth"
                    )

                    st.caption(
                        "Cumulative quantities are calculated "
                        "from each side's best price outward. "
                        "Bid depth accumulates toward lower "
                        "prices; ask depth accumulates toward "
                        "higher prices. Chart lines join "
                        "discrete recorded price levels."
                    )

                    left, right = st.columns(2)

                    with left:

                        st.markdown(
                            "**Bid-side cumulative depth**"
                        )

                        if bids.empty:
                            st.info(
                                "No recorded bid levels."
                            )

                        else:
                            bid_chart = (
                                bids.sort_values(
                                    "price"
                                )
                                .set_index("price")[
                                    ["cumulative_size"]
                                ]
                            )

                            st.line_chart(
                                bid_chart,
                                width="stretch",
                                height=320,
                                x_label="Bid price",
                                y_label=(
                                    "Cumulative contract quantity"
                                ),
                            )

                    with right:

                        st.markdown(
                            "**Ask-side cumulative depth**"
                        )

                        if asks.empty:
                            st.info(
                                "No recorded ask levels."
                            )

                        else:
                            ask_chart = (
                                asks.sort_values(
                                    "price"
                                )
                                .set_index("price")[
                                    ["cumulative_size"]
                                ]
                            )

                            st.line_chart(
                                ask_chart,
                                width="stretch",
                                height=320,
                                x_label="Ask price",
                                y_label=(
                                    "Cumulative contract quantity"
                                ),
                            )

                    # -----------------------------------------
                    # Individual price-level liquidity
                    # -----------------------------------------

                    st.subheader(
                        "Liquidity by Recorded Price Level"
                    )

                    st.caption(
                        "Individual quoted contract quantities "
                        "at each stored price level. These are "
                        "not estimates of fillable size."
                    )

                    left, right = st.columns(2)

                    with left:

                        st.markdown(
                            "**Bid-side level quantities**"
                        )

                        if bids.empty:
                            st.info(
                                "No recorded bid levels."
                            )

                        else:
                            bid_levels = (
                                bids.sort_values(
                                    "price"
                                )
                                .set_index("price")[
                                    ["size"]
                                ]
                            )

                            st.bar_chart(
                                bid_levels,
                                width="stretch",
                                height=320,
                                x_label="Bid price",
                                y_label="Contract quantity",
                            )

                    with right:

                        st.markdown(
                            "**Ask-side level quantities**"
                        )

                        if asks.empty:
                            st.info(
                                "No recorded ask levels."
                            )

                        else:
                            ask_levels = (
                                asks.sort_values(
                                    "price"
                                )
                                .set_index("price")[
                                    ["size"]
                                ]
                            )

                            st.bar_chart(
                                ask_levels,
                                width="stretch",
                                height=320,
                                x_label="Ask price",
                                y_label="Contract quantity",
                            )

                    # -----------------------------------------
                    # Underlying depth observations
                    # -----------------------------------------

                    with st.expander(
                        "View underlying recorded price levels"
                    ):
                        st.dataframe(
                            depth,
                            width="stretch",
                            hide_index=True,
                        )

                    st.caption(
                        "This view describes one stored "
                        "snapshot. It does not verify stream "
                        "completeness, intervening updates, "
                        "independent replay, or live trading "
                        "availability."
                    )


# -------------------------------------------------------------
# Collection Health
# -------------------------------------------------------------

with health_tab:

    st.subheader(
        "Collection Session History"
    )

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
    "Exploratory research only. Stored observations "
    "are not independently verified trading signals."
)
