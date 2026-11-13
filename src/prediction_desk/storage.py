import json
from datetime import datetime, timezone
from prediction_desk.spot import SpotTrade
from prediction_desk.market_signals import MarketShock
import sqlite3
from pathlib import Path

from prediction_desk.models import OrderBook


class Storage:

    def __init__(self, database_path):
        self.database_path = Path(database_path)

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.connection = sqlite3.connect(
            self.database_path,
            timeout=30.0,
        )

        try:
            self.connection.execute(
                "PRAGMA foreign_keys = ON"
            )

            self.connection.execute(
                "PRAGMA busy_timeout = 30000"
            )

        except Exception:
            self.connection.close()
            raise

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


    def initialize(self):
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS order_book_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_id TEXT NOT NULL,
                    source_timestamp_ms INTEGER NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    best_bid TEXT,
                    best_ask TEXT,
                    spread TEXT,
                    book_hash TEXT NOT NULL,

                    UNIQUE (
                        token_id,
                        source_timestamp_ms,
                        book_hash
                    )
                )
                """
            )

            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS order_book_levels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER NOT NULL,
                    side TEXT NOT NULL
                        CHECK (side IN ('BUY', 'SELL')),
                    price TEXT NOT NULL,
                    size TEXT NOT NULL,
                    FOREIGN KEY (snapshot_id)
                        REFERENCES order_book_snapshots(id)
                        ON DELETE CASCADE,
                    UNIQUE (snapshot_id, side, price)
                )
                """
            )

            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS markets (
                    market_id TEXT PRIMARY KEY,
                    event_title TEXT NOT NULL,
                    question TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    condition_id TEXT NOT NULL,
                    end_date TEXT NOT NULL
                )
                """
            )

            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS outcomes (
                    token_id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    outcome_name TEXT NOT NULL,

                    FOREIGN KEY (market_id)
                        REFERENCES markets(market_id)
                )
                """
            )


            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS markets (
                    market_id TEXT PRIMARY KEY,
                    event_title TEXT NOT NULL,
                    question TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    condition_id TEXT NOT NULL,
                    end_date TEXT NOT NULL
                )
                """
            )

            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS outcomes (
                    token_id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    outcome_name TEXT NOT NULL,

                    FOREIGN KEY (market_id)
                        REFERENCES markets(market_id)
                )
                """
            )


            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS market_shocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT NOT NULL,
                    event_timestamp_ms INTEGER NOT NULL,
                    magnitude TEXT NOT NULL,
                    outcome_details_json TEXT NOT NULL,
                    detected_at_utc TEXT NOT NULL,
                    UNIQUE (market_id, event_timestamp_ms),
                    FOREIGN KEY (market_id)
                        REFERENCES markets(market_id)
                )
                """
            )

            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS spot_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset TEXT NOT NULL,
                    trade_id INTEGER NOT NULL,
                    trade_timestamp_ms INTEGER NOT NULL,
                    price_usd TEXT NOT NULL,
                    size TEXT NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    UNIQUE (asset, trade_id)
                )
                """
            )

            self.connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_spot_trades_asset_time
                ON spot_trades (asset, trade_timestamp_ms)
                """
            )

            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS spot_collection_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset TEXT NOT NULL,
                    started_at_utc TEXT NOT NULL,
                    completed_at_utc TEXT NOT NULL,
                    status TEXT NOT NULL,
                    fetched INTEGER NOT NULL,
                    inserted INTEGER NOT NULL,
                    first_trade_id INTEGER,
                    last_trade_id INTEGER,
                    first_trade_timestamp_ms INTEGER,
                    last_trade_timestamp_ms INTEGER,
                    overlap_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            self.connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_spot_runs_asset
                ON spot_collection_runs (asset, id)
                """
            )

            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS spot_stream_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at_utc TEXT NOT NULL,
                    completed_at_utc TEXT,
                    status TEXT NOT NULL,
                    termination_reason TEXT,
                    connection_attempts INTEGER NOT NULL DEFAULT 0,
                    messages_received INTEGER NOT NULL DEFAULT 0,
                    trades_received INTEGER NOT NULL DEFAULT 0,
                    trades_inserted INTEGER NOT NULL DEFAULT 0,
                    ignored_messages INTEGER NOT NULL DEFAULT 0,
                    potential_id_gaps INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS market_price_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_id TEXT NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    best_bid TEXT,
                    best_ask TEXT
                )
                """
            )

            columns = {
                row[1]
                for row in self.connection.execute(
                    "PRAGMA table_info(market_price_changes)"
                )
            }

            if "source_timestamp_ms" not in columns:
                self.connection.execute(
                    """
                    ALTER TABLE market_price_changes
                    ADD COLUMN source_timestamp_ms INTEGER
                    """
                )

            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS market_level_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_id TEXT NOT NULL,
                    source_timestamp_ms INTEGER,
                    observed_at_utc TEXT NOT NULL,
                    price TEXT NOT NULL,
                    size TEXT NOT NULL,
                    side TEXT NOT NULL
                        CHECK (side IN ('BUY', 'SELL'))
                )
                """
            )

            self.connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_market_level_updates_token_time
                ON market_level_updates (
                    token_id,
                    source_timestamp_ms
                )
                """
            )


            self.connection.execute(
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

            for table_name in (
                "order_book_snapshots",
                "market_price_changes",
                "market_level_updates",
            ):
                existing_columns = {
                    row[1]
                    for row in self.connection.execute(
                        f"PRAGMA table_info({table_name})"
                    )
                }

                if "stream_session_id" not in existing_columns:
                    self.connection.execute(
                        f"""
                        ALTER TABLE {table_name}
                        ADD COLUMN stream_session_id INTEGER
                            REFERENCES polymarket_stream_sessions(id)
                        """
                    )

                if "message_sequence" not in existing_columns:
                    self.connection.execute(
                        f"""
                        ALTER TABLE {table_name}
                        ADD COLUMN message_sequence INTEGER
                        """
                    )

                self.connection.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS
                        idx_{table_name}_session_sequence
                    ON {table_name} (
                        stream_session_id,
                        message_sequence,
                        id
                    )
                    """
                )



    def save_market_shock(self, event: MarketShock):
        if not isinstance(event, MarketShock):
            raise TypeError("event must be a MarketShock")

        if not event.outcome_shocks:
            raise ValueError(
                "Market shock must have supporting outcomes"
            )

        details = [
            {
                "token_id": shock.token_id,
                "outcome_name": shock.outcome_name,
                "previous_timestamp_ms": (
                    shock.previous_timestamp_ms
                ),
                "current_timestamp_ms": (
                    shock.current_timestamp_ms
                ),
                "previous_midpoint": str(
                    shock.previous_midpoint
                ),
                "current_midpoint": str(
                    shock.current_midpoint
                ),
                "change": str(shock.change),
            }
            for shock in event.outcome_shocks
        ]

        detected_at_utc = datetime.now(
            timezone.utc
        ).isoformat()

        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT OR IGNORE INTO market_shocks (
                    market_id,
                    event_timestamp_ms,
                    magnitude,
                    outcome_details_json,
                    detected_at_utc
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.market_id,
                    event.timestamp_ms,
                    str(event.magnitude),
                    json.dumps(details, sort_keys=True),
                    detected_at_utc,
                ),
            )

        return cursor.rowcount == 1

    def count_market_shocks(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM market_shocks"
        ).fetchone()[0]

    def save_order_book(
            self,
            book: OrderBook,
            source_timestamp_ms: int,
            observed_at_utc: str,
            book_hash: str,
            stream_session_id=None,
            message_sequence=None,
    ):
        if not isinstance(book, OrderBook):
            raise TypeError("book must be an OrderBook")

        if (
                type(source_timestamp_ms) is not int
                or source_timestamp_ms <= 0
        ):
            raise ValueError(
                "source_timestamp_ms must be a positive integer"
            )

        if not observed_at_utc:
            raise ValueError("observed_at_utc is required")

        if not book_hash:
            raise ValueError("book_hash is required")

        if (
                book.best_bid is not None
                and book.best_ask is not None
                and book.best_bid >= book.best_ask
        ):
            raise ValueError("Order book is locked or crossed")

        # Validate every level before opening the transaction.
        # This also rejects duplicate side/price entries.
        from decimal import Decimal

        level_rows = []
        seen_levels = set()

        for side, levels in (
                ("BUY", book.bids),
                ("SELL", book.asks),
        ):
            for level in levels:
                price = level.price
                size = level.size

                if (
                        not isinstance(price, Decimal)
                        or not price.is_finite()
                        or not Decimal("0") < price < Decimal("1")
                ):
                    raise ValueError("Invalid book level price")

                if (
                        not isinstance(size, Decimal)
                        or not size.is_finite()
                        or size < 0
                ):
                    raise ValueError("Invalid book level size")

                key = (side, price)

                if key in seen_levels:
                    raise ValueError("Duplicate book level")

                seen_levels.add(key)

                level_rows.append(
                    (side, str(price), str(size))
                )


        if (stream_session_id is None) != (message_sequence is None):
            raise ValueError(
                "Session ID and message sequence must be supplied together"
            )

        if stream_session_id is not None:
            if type(stream_session_id) is not int or stream_session_id <= 0:
                raise ValueError("Invalid stream session ID")

            if type(message_sequence) is not int or message_sequence <= 0:
                raise ValueError("Invalid message sequence")


        if self.connection.in_transaction:
            raise RuntimeError(
                "Atomic save requires no active transaction"
            )

        try:
            self.connection.execute("BEGIN IMMEDIATE")

            cursor = self.connection.execute(
                """
                INSERT OR IGNORE INTO order_book_snapshots (
                    token_id,
                    source_timestamp_ms,
                    observed_at_utc,
                    best_bid,
                    best_ask,
                    spread,
                    book_hash,
                    stream_session_id,
                    message_sequence
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    book.token_id,
                    source_timestamp_ms,
                    observed_at_utc,
                    str(book.best_bid)
                    if book.best_bid is not None
                    else None,
                    str(book.best_ask)
                    if book.best_ask is not None
                    else None,
                    str(book.spread)
                    if book.spread is not None
                    else None,
                    book_hash,
                    stream_session_id,
                    message_sequence,
                ),
            )

            inserted = cursor.rowcount == 1

            if inserted:
                snapshot_id = cursor.lastrowid

                self.connection.executemany(
                    """
                    INSERT INTO order_book_levels (
                        snapshot_id,
                        side,
                        price,
                        size
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (snapshot_id, side, price, size)
                        for side, price, size in level_rows
                    ],
                )

            self.connection.commit()

        except Exception:
            self.connection.rollback()
            raise

        return inserted

    def count_snapshots(self):
        cursor = self.connection.execute(
            "SELECT COUNT(*) FROM order_book_snapshots"
        )
        return cursor.fetchone()[0]


    def save_market(self, market):
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO markets (
                    market_id,
                    event_title,
                    question,
                    asset,
                    market_type,
                    condition_id,
                    end_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market_id) DO UPDATE SET
                    event_title = excluded.event_title,
                    question = excluded.question,
                    asset = excluded.asset,
                    market_type = excluded.market_type,
                    condition_id = excluded.condition_id,
                    end_date = excluded.end_date
                """,
                (
                    market.market_id,
                    market.event_title,
                    market.question,
                    market.asset,
                    market.market_type,
                    market.condition_id,
                    market.end_date,
                ),
            )

            for outcome_name, token_id in market.outcome_tokens:
                self.connection.execute(
                    """
                    INSERT INTO outcomes (
                        token_id,
                        market_id,
                        outcome_name
                    )
                    VALUES (?, ?, ?)
                    ON CONFLICT(token_id) DO UPDATE SET
                        market_id = excluded.market_id,
                        outcome_name = excluded.outcome_name
                    """,
                    (
                        token_id,
                        market.market_id,
                        outcome_name,
                    ),
                )

    def count_markets(self):
        cursor = self.connection.execute(
            "SELECT COUNT(*) FROM markets"
        )
        return cursor.fetchone()[0]

    def count_outcomes(self):
        cursor = self.connection.execute(
            "SELECT COUNT(*) FROM outcomes"
        )
        return cursor.fetchone()[0]


    def get_outcome_history(self, token_id, limit=100):
        token_id = str(token_id)

        if not token_id.isdigit():
            raise ValueError("Invalid token ID")

        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit <= 0
        ):
            raise ValueError("limit must be positive")

        cursor = self.connection.execute(
            """
            SELECT
                s.token_id,
                o.market_id,
                o.outcome_name,
                s.source_timestamp_ms,
                s.observed_at_utc,
                s.best_bid,
                s.best_ask,
                s.spread
            FROM order_book_snapshots AS s
            JOIN outcomes AS o
                ON s.token_id = o.token_id
            WHERE s.token_id = ?
            ORDER BY
                s.source_timestamp_ms DESC,
                s.id DESC
            LIMIT ?
            """,
            (token_id, limit),
        )

        columns = [
            description[0]
            for description in cursor.description
        ]

        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]


    def save_spot_trades(self, trades):
        trades = list(trades)

        if not all(
            isinstance(trade, SpotTrade)
            for trade in trades
        ):
            raise TypeError("Expected SpotTrade objects")

        observed_at_utc = datetime.now(
            timezone.utc
        ).isoformat()

        rows = [
            (
                trade.asset,
                trade.trade_id,
                trade.timestamp_ms,
                str(trade.price_usd),
                str(trade.size),
                observed_at_utc,
            )
            for trade in trades
        ]

        before = self.connection.total_changes

        with self.connection:
            self.connection.executemany(
                """
                INSERT OR IGNORE INTO spot_trades (
                    asset,
                    trade_id,
                    trade_timestamp_ms,
                    price_usd,
                    size,
                    observed_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

        inserted = (
            self.connection.total_changes - before
        )

        return inserted

    def count_spot_trades(self, asset=None):
        if asset is not None:
            if asset not in {"BTC", "ETH"}:
                raise ValueError("Unsupported asset")

            return self.connection.execute(
                """
                SELECT COUNT(*)
                FROM spot_trades
                WHERE asset = ?
                """,
                (asset,),
            ).fetchone()[0]

        return self.connection.execute(
            """
            SELECT COUNT(*)
            FROM spot_trades
            """
        ).fetchone()[0]

    def get_spot_trades(
        self,
        asset,
        start_timestamp_ms,
        end_timestamp_ms,
    ):
        if asset not in {"BTC", "ETH"}:
            raise ValueError("Unsupported asset")

        if (
            not isinstance(start_timestamp_ms, int)
            or isinstance(start_timestamp_ms, bool)
            or not isinstance(end_timestamp_ms, int)
            or isinstance(end_timestamp_ms, bool)
            or start_timestamp_ms <= 0
            or end_timestamp_ms <= start_timestamp_ms
        ):
            raise ValueError("Invalid time window")

        cursor = self.connection.execute(
            """
            SELECT
                asset,
                trade_id,
                trade_timestamp_ms,
                price_usd,
                size,
                observed_at_utc
            FROM spot_trades
            WHERE asset = ?
              AND trade_timestamp_ms >= ?
              AND trade_timestamp_ms <= ?
            ORDER BY trade_timestamp_ms ASC, trade_id ASC
            """,
            (
                asset,
                start_timestamp_ms,
                end_timestamp_ms,
            ),
        )

        columns = [
            description[0]
            for description in cursor.description
        ]

        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]


    def save_spot_collection_run(
        self,
        asset,
        started_at_utc,
        completed_at_utc,
        status,
        fetched,
        inserted,
        first_trade_id=None,
        last_trade_id=None,
        first_trade_timestamp_ms=None,
        last_trade_timestamp_ms=None,
        overlap_count=0,
    ):
        if asset not in {"BTC", "ETH"}:
            raise ValueError("Unsupported asset")

        if status not in {
            "success",
            "api_error",
            "empty_response",
        }:
            raise ValueError("Invalid collection status")

        for value in (fetched, inserted, overlap_count):
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                raise ValueError("Invalid collection count")

        if inserted > fetched or overlap_count > fetched:
            raise ValueError("Inconsistent collection counts")

        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO spot_collection_runs (
                    asset,
                    started_at_utc,
                    completed_at_utc,
                    status,
                    fetched,
                    inserted,
                    first_trade_id,
                    last_trade_id,
                    first_trade_timestamp_ms,
                    last_trade_timestamp_ms,
                    overlap_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset,
                    started_at_utc,
                    completed_at_utc,
                    status,
                    fetched,
                    inserted,
                    first_trade_id,
                    last_trade_id,
                    first_trade_timestamp_ms,
                    last_trade_timestamp_ms,
                    overlap_count,
                ),
            )

        return cursor.lastrowid

    def get_latest_spot_collection_run(self, asset):
        if asset not in {"BTC", "ETH"}:
            raise ValueError("Unsupported asset")

        cursor = self.connection.execute(
            """
            SELECT *
            FROM spot_collection_runs
            WHERE asset = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (asset,),
        )

        row = cursor.fetchone()

        if row is None:
            return None

        columns = [
            description[0]
            for description in cursor.description
        ]

        return dict(zip(columns, row))

    def count_spot_collection_runs(self, asset=None):
        if asset is not None:
            if asset not in {"BTC", "ETH"}:
                raise ValueError("Unsupported asset")

            return self.connection.execute(
                """
                SELECT COUNT(*)
                FROM spot_collection_runs
                WHERE asset = ?
                """,
                (asset,),
            ).fetchone()[0]

        return self.connection.execute(
            """
            SELECT COUNT(*)
            FROM spot_collection_runs
            """
        ).fetchone()[0]

    def start_spot_stream_session(self, started_at_utc):
        cursor = self.connection.execute(
            """
            INSERT INTO spot_stream_sessions (
                started_at_utc,
                status
            )
            VALUES (?, 'running')
            """,
            (started_at_utc,),
        )

        self.connection.commit()
        return cursor.lastrowid

    def finish_spot_stream_session(
            self,
            session_id,
            completed_at_utc,
            status,
            termination_reason,
            connection_attempts,
            messages_received,
            trades_received,
            trades_inserted,
            ignored_messages,
            potential_id_gaps,
    ):
        with self.connection:
            cursor = self.connection.execute(
                """
                UPDATE spot_stream_sessions
                SET
                    completed_at_utc = ?,
                    status = ?,
                    termination_reason = ?,
                    connection_attempts = ?,
                    messages_received = ?,
                    trades_received = ?,
                    trades_inserted = ?,
                    ignored_messages = ?,
                    potential_id_gaps = ?
                WHERE id = ?
                  AND status = 'running'
                """,
                (
                    completed_at_utc,
                    status,
                    termination_reason,
                    connection_attempts,
                    messages_received,
                    trades_received,
                    trades_inserted,
                    ignored_messages,
                    potential_id_gaps,
                    session_id,
                ),
            )

            if cursor.rowcount != 1:
                raise ValueError(
                    "Stream session not found or already finished"
                )

    def get_latest_spot_stream_session(self):
        cursor = self.connection.execute(
            """
            SELECT
                id,
                started_at_utc,
                completed_at_utc,
                status,
                termination_reason,
                connection_attempts,
                messages_received,
                trades_received,
                trades_inserted,
                ignored_messages,
                potential_id_gaps
            FROM spot_stream_sessions
            ORDER BY id DESC
            LIMIT 1
            """
        )

        row = cursor.fetchone()

        if row is None:
            return None

        columns = [
            item[0]
            for item in cursor.description
        ]

        return dict(zip(columns, row))

    def save_market_price_change(
            self,
            token_id: str,
            best_bid,
            best_ask,
            observed_at_utc: str,
            source_timestamp_ms: int | None = None,
    ) -> bool:
        from decimal import Decimal

        if not isinstance(token_id, str) or not token_id.isdigit():
            raise ValueError("Invalid token ID")

        if not observed_at_utc:
            raise ValueError("Observation timestamp required")

        if source_timestamp_ms is not None:
            if (
                    type(source_timestamp_ms) is not int
                    or source_timestamp_ms <= 0
            ):
                raise ValueError(
                    "source_timestamp_ms must be a positive integer"
                )

        for value in (best_bid, best_ask):
            if value is not None:
                if not isinstance(value, Decimal):
                    raise TypeError("Prices must be Decimal")

                if not value.is_finite() or not 0 <= value <= 1:
                    raise ValueError("Invalid probability price")

        if (
                best_bid is not None
                and best_ask is not None
                and best_bid > best_ask
        ):
            raise ValueError("Crossed best bid and ask")

        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO market_price_changes (
                    token_id,
                    source_timestamp_ms,
                    observed_at_utc,
                    best_bid,
                    best_ask
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    token_id,
                    source_timestamp_ms,
                    observed_at_utc,
                    str(best_bid) if best_bid is not None else None,
                    str(best_ask) if best_ask is not None else None,
                ),
            )

        return cursor.rowcount == 1

    def count_market_price_changes(self) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM market_price_changes"
        ).fetchone()

        return row[0]

    def save_market_level_update(
            self,
            token_id: str,
            price,
            size,
            side: str,
            observed_at_utc: str,
            source_timestamp_ms: int | None = None,
    ) -> bool:
        from decimal import Decimal

        if not isinstance(token_id, str) or not token_id.isdigit():
            raise ValueError("Invalid token ID")

        if not observed_at_utc:
            raise ValueError("Observation timestamp required")

        if source_timestamp_ms is not None:
            if (
                    type(source_timestamp_ms) is not int
                    or source_timestamp_ms <= 0
            ):
                raise ValueError("Invalid source timestamp")

        if (
                not isinstance(price, Decimal)
                or not price.is_finite()
                or not Decimal("0") < price < Decimal("1")
        ):
            raise ValueError("Invalid level price")

        if (
                not isinstance(size, Decimal)
                or not size.is_finite()
                or size < 0
        ):
            raise ValueError("Invalid level size")

        if side not in ("BUY", "SELL"):
            raise ValueError("Invalid level side")

        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO market_level_updates (
                    token_id,
                    source_timestamp_ms,
                    observed_at_utc,
                    price,
                    size,
                    side
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    token_id,
                    source_timestamp_ms,
                    observed_at_utc,
                    str(price),
                    str(size),
                    side,
                ),
            )

        return cursor.rowcount == 1



    def save_atomic_market_price_change(
            self,
            token_id: str,
            best_bid,
            best_ask,
            observed_at_utc: str,
            source_timestamp_ms: int | None = None,
            price=None,
            size=None,
            side=None,
            stream_session_id=None,
            message_sequence=None,
    ) -> bool:

        from decimal import Decimal

        if not isinstance(token_id, str) or not token_id.isdigit():
            raise ValueError("Invalid token ID")

        if not observed_at_utc:
            raise ValueError("Observation timestamp required")

        if source_timestamp_ms is not None:
            if (
                type(source_timestamp_ms) is not int
                or source_timestamp_ms <= 0
            ):
                raise ValueError("Invalid source timestamp")

        for value in (best_bid, best_ask):
            if value is not None:
                if (
                    not isinstance(value, Decimal)
                    or not value.is_finite()
                    or not Decimal("0") <= value <= Decimal("1")
                ):
                    raise ValueError("Invalid probability price")

        if (
            best_bid is not None
            and best_ask is not None
            and best_bid > best_ask
        ):
            raise ValueError("Crossed best bid and ask")

        has_level = any(
            value is not None
            for value in (price, size, side)
        )

        if has_level:
            if (
                price is None
                or size is None
                or side is None
            ):
                raise ValueError("Incomplete level update")

            if (
                not isinstance(price, Decimal)
                or not price.is_finite()
                or not Decimal("0") < price < Decimal("1")
            ):
                raise ValueError("Invalid level price")

            if (
                not isinstance(size, Decimal)
                or not size.is_finite()
                or size < 0
            ):
                raise ValueError("Invalid level size")

            if side not in ("BUY", "SELL"):
                raise ValueError("Invalid level side")


        if (stream_session_id is None) != (message_sequence is None):
            raise ValueError(
                "Session ID and message sequence must be supplied together"
            )

        if stream_session_id is not None:
            if type(stream_session_id) is not int or stream_session_id <= 0:
                raise ValueError("Invalid stream session ID")

            if type(message_sequence) is not int or message_sequence <= 0:
                raise ValueError("Invalid message sequence")


        # Explicit transaction boundary.
        # Both inserts succeed or both are rolled back.
        if self.connection.in_transaction:
            raise RuntimeError(
                "Atomic save requires no active transaction"
            )

        try:
            self.connection.execute("BEGIN IMMEDIATE")

            cursor = self.connection.execute(
                """
                INSERT INTO market_price_changes (
                    token_id,
                    source_timestamp_ms,
                    observed_at_utc,
                    best_bid,
                    best_ask,
                    stream_session_id,
                    message_sequence
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token_id,
                    source_timestamp_ms,
                    observed_at_utc,
                    str(best_bid) if best_bid is not None else None,
                    str(best_ask) if best_ask is not None else None,
                    stream_session_id,
                    message_sequence,
                ),
            )

            if has_level:

                self.connection.execute(
                    """
                    INSERT INTO market_level_updates (
                        token_id,
                        source_timestamp_ms,
                        observed_at_utc,
                        price,
                        size,
                        side,
                        stream_session_id,
                        message_sequence
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        token_id,
                        source_timestamp_ms,
                        observed_at_utc,
                        str(price),
                        str(size),
                        side,
                        stream_session_id,
                        message_sequence,
                    ),
                )

            self.connection.commit()

        except Exception:
            self.connection.rollback()
            raise

        return cursor.rowcount == 1