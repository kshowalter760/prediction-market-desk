
from datetime import datetime, timezone
from pathlib import Path

from prediction_desk.spot_stream import collect_live_stream
from prediction_desk.storage import Storage
from prediction_desk.stream_audit import assess_stream_continuity


DATABASE_PATH = Path("data/prediction_markets.db")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def main():
    print("\nCoinbase WebSocket trade collector")
    print("Products: BTC-USD, ETH-USD")
    print("Maximum messages: 100")
    print("Receive timeout: 10 seconds")

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    received_trades = []

    with Storage(DATABASE_PATH) as storage:
        storage.initialize()

        session_id = storage.start_spot_stream_session(
            utc_now()
        )

        before = storage.count_spot_trades()

        try:
            result = collect_live_stream(
                storage,
                max_messages=100,
                receive_timeout_seconds=10,
                on_trade=received_trades.append,
            )

            audit = assess_stream_continuity(
                received_trades
            )

            storage.finish_spot_stream_session(
                session_id=session_id,
                completed_at_utc=utc_now(),
                status="completed",
                termination_reason=(
                    "message_limit"
                    if result.messages_received == 100
                    else "receive_timeout"
                ),
                connection_attempts=1,
                messages_received=result.messages_received,
                trades_received=result.trades_received,
                trades_inserted=result.trades_inserted,
                ignored_messages=result.ignored_messages,
                potential_id_gaps=audit.total_potential_gaps,
            )

        except Exception as exc:
            storage.finish_spot_stream_session(
                session_id=session_id,
                completed_at_utc=utc_now(),
                status="failed",
                termination_reason=type(exc).__name__,
                connection_attempts=1,
                messages_received=0,
                trades_received=0,
                trades_inserted=0,
                ignored_messages=0,
                potential_id_gaps=0,
            )
            raise

        after = storage.count_spot_trades()

        print("\nStreaming results")
        print("Messages:", result.messages_received)
        print("Trade messages:", result.trades_received)
        print("Inserted:", result.trades_inserted)
        print("Ignored:", result.ignored_messages)

        print("\nDatabase")
        print("Before:", before)
        print("After:", after)
        print("BTC:", storage.count_spot_trades("BTC"))
        print("ETH:", storage.count_spot_trades("ETH"))

        print("\nTrade continuity audit")

        for report in (audit.btc, audit.eth):
            print(f"\n{report.asset}")
            print("Status:", report.status)
            print("Unique trades:", report.unique_trades)
            print("Duplicate IDs:", report.duplicate_ids)
            print("Potential gaps:", len(report.gaps))

            for gap in report.gaps[:5]:
                print(
                    f"  {gap.previous_trade_id} -> "
                    f"{gap.current_trade_id} | "
                    f"Unobserved IDs: {gap.missing_id_count}"
                )

        print("\nCombined continuity summary")
        print(
            "Potential gaps:",
            audit.total_potential_gaps,
        )
        print(
            "Unobserved IDs:",
            audit.total_missing_ids,
        )

        print("\nPersisted session audit")
        latest = storage.get_latest_spot_stream_session()

        print("Session ID:", latest["id"])
        print("Status:", latest["status"])
        print(
            "Termination reason:",
            latest["termination_reason"],
        )
        print(
            "Connection attempts:",
            latest["connection_attempts"],
        )
        print(
            "Recorded trades:",
            latest["trades_inserted"],
        )


if __name__ == "__main__":
    main()
