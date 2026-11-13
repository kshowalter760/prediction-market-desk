
from bisect import bisect_right
from dataclasses import dataclass
from decimal import Decimal
import sqlite3

from prediction_desk.spot import SpotTrade
from prediction_desk.trade_alignment import align_spot_trade


@dataclass(frozen=True)
class CrossMarketObservation:
    token_id: str
    asset: str
    outcome_name: str
    event_type: str
    event_timestamp_ms: int
    polymarket_observed_at_utc: str
    best_bid: Decimal | None
    best_ask: Decimal | None
    midpoint: Decimal | None
    spot_trade_id: int | None
    spot_price_usd: Decimal | None
    spot_timestamp_ms: int | None
    spot_observed_at_utc: str | None
    spot_age_ms: int | None
    status: str


def calculate_midpoint(bid, ask):
    if bid is None or ask is None:
        return None

    bid = Decimal(str(bid))
    ask = Decimal(str(ask))

    if (
        not bid.is_finite()
        or not ask.is_finite()
        or not Decimal("0") <= bid <= ask <= Decimal("1")
    ):
        return None

    return (bid + ask) / Decimal("2")


def load_spot_history(connection):
    rows = connection.execute(
        """
        SELECT
            asset,
            trade_id,
            trade_timestamp_ms,
            price_usd,
            size,
            observed_at_utc
        FROM spot_trades
        WHERE trade_timestamp_ms IS NOT NULL
        ORDER BY asset, trade_timestamp_ms, trade_id, id
        """
    ).fetchall()

    history = {}

    for row in rows:
        trade = SpotTrade(
            asset=row["asset"],
            trade_id=row["trade_id"],
            timestamp_ms=row["trade_timestamp_ms"],
            price_usd=Decimal(row["price_usd"]),
            size=Decimal(row["size"]),
        )

        history.setdefault(trade.asset, []).append(
            (trade, row["observed_at_utc"])
        )

    return history


def load_market_events(connection):
    return connection.execute(
        """
        SELECT
            o.token_id,
            m.asset,
            o.outcome_name,
            'book' AS event_type,
            b.source_timestamp_ms AS event_timestamp_ms,
            b.observed_at_utc,
            b.best_bid,
            b.best_ask
        FROM order_book_snapshots AS b
        JOIN outcomes AS o
            ON o.token_id = b.token_id
        JOIN markets AS m
            ON m.market_id = o.market_id
        WHERE b.source_timestamp_ms IS NOT NULL

        UNION ALL

        SELECT
            o.token_id,
            m.asset,
            o.outcome_name,
            'price_change' AS event_type,
            p.source_timestamp_ms AS event_timestamp_ms,
            p.observed_at_utc,
            p.best_bid,
            p.best_ask
        FROM market_price_changes AS p
        JOIN outcomes AS o
            ON o.token_id = p.token_id
        JOIN markets AS m
            ON m.market_id = o.market_id
        WHERE p.source_timestamp_ms IS NOT NULL

        ORDER BY 5, 1, 4
        """
    ).fetchall()


def build_cross_market_dataset(
    connection,
    max_age_ms=5000,
):
    if (
        isinstance(max_age_ms, bool)
        or not isinstance(max_age_ms, int)
        or max_age_ms < 0
    ):
        raise ValueError(
            "max_age_ms must be a nonnegative integer"
        )

    connection.row_factory = sqlite3.Row

    history = load_spot_history(connection)
    events = load_market_events(connection)

    # Prepare timestamp indexes once per asset.
    indexes = {}

    for asset, entries in history.items():
        indexes[asset] = [
            trade.timestamp_ms
            for trade, _ in entries
        ]

    results = []

    for event in events:
        asset = event["asset"]
        timestamp = event["event_timestamp_ms"]

        entries = history.get(asset, [])
        timestamps = indexes.get(asset, [])

        position = bisect_right(
            timestamps,
            timestamp,
        ) - 1

        aligned = None
        observed_at = None
        age_ms = None

        if position < 0:
            status = "no_prior_spot"

        else:
            candidate, observed_at = entries[position]

            age_ms = (
                timestamp - candidate.timestamp_ms
            )

            if age_ms > max_age_ms:
                status = "stale_spot"

            else:
                # Reuse our existing, tested matcher.
                aligned = align_spot_trade(
                    [candidate],
                    event_timestamp_ms=timestamp,
                    max_age_ms=max_age_ms,
                )

                status = "matched"

        candidate_trade = (
            entries[position][0]
            if position >= 0
            else None
        )

        results.append(
            CrossMarketObservation(
                token_id=event["token_id"],
                asset=asset,
                outcome_name=event["outcome_name"],
                event_type=event["event_type"],
                event_timestamp_ms=timestamp,
                polymarket_observed_at_utc=event[
                    "observed_at_utc"
                ],
                best_bid=(
                    Decimal(event["best_bid"])
                    if event["best_bid"] is not None
                    else None
                ),
                best_ask=(
                    Decimal(event["best_ask"])
                    if event["best_ask"] is not None
                    else None
                ),
                midpoint=calculate_midpoint(
                    event["best_bid"],
                    event["best_ask"],
                ),
                spot_trade_id=(
                    candidate_trade.trade_id
                    if candidate_trade is not None
                    else None
                ),
                spot_price_usd=(
                    candidate_trade.price_usd
                    if candidate_trade is not None
                    else None
                ),
                spot_timestamp_ms=(
                    candidate_trade.timestamp_ms
                    if candidate_trade is not None
                    else None
                ),
                spot_observed_at_utc=observed_at,
                spot_age_ms=age_ms,
                status=status,
            )
        )

    return results
