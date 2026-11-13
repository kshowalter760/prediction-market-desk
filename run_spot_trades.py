
from datetime import datetime, timezone

from prediction_desk.spot import (
    CoinbaseSpotClient,
    SpotAPIError,
)


def format_time(timestamp_ms):
    return datetime.fromtimestamp(
        timestamp_ms / 1000,
        tz=timezone.utc,
    ).isoformat()


def main():
    print("\nCoinbase sub-minute trade observations")

    with CoinbaseSpotClient() as client:
        for asset in ("BTC", "ETH"):
            try:
                trades = client.get_recent_trades(
                    asset,
                    limit=100,
                )
            except SpotAPIError as exc:
                print(f"\n{asset}: {exc}")
                continue

            print(f"\n{asset}: {len(trades)} trades")

            if not trades:
                print("No trades returned")
                continue

            first = trades[0]
            last = trades[-1]

            print(
                f"Sample begins: "
                f"{format_time(first.timestamp_ms)}"
            )
            print(
                f"Sample ends:   "
                f"{format_time(last.timestamp_ms)}"
            )

            duration_seconds = (
                last.timestamp_ms - first.timestamp_ms
            ) / 1000

            print(
                f"Sample duration: "
                f"{duration_seconds:.3f} seconds"
            )

            print("Latest 3 trades:")

            for trade in trades[-3:]:
                print(
                    f"  {format_time(trade.timestamp_ms)} "
                    f"${trade.price_usd:,.2f} "
                    f"Size={trade.size}"
                )


if __name__ == "__main__":
    main()
