
from datetime import datetime, timezone, timedelta

from prediction_desk.spot import (
    CoinbaseSpotClient,
    SpotAPIError,
)


def main():
    end = datetime.now(timezone.utc) - timedelta(minutes=2)
    end = end.replace(second=0, microsecond=0)
    start = end - timedelta(minutes=10)

    print("\nHistorical spot-market candles")
    print(f"Start: {start.isoformat()}")
    print(f"End:   {end.isoformat()}")

    with CoinbaseSpotClient() as client:
        for asset in ("BTC", "ETH"):
            try:
                candles = client.get_historical_candles(
                    asset=asset,
                    start=start,
                    end=end,
                )
            except SpotAPIError as exc:
                print(f"\n{asset}: {exc}")
                continue

            print(f"\n{asset}: {len(candles)} candles")

            for candle in candles[-3:]:
                candle_time = datetime.fromtimestamp(
                    candle.start_timestamp_s,
                    tz=timezone.utc,
                )
                print(
                    f"  {candle_time.isoformat()} "
                    f"Open=${candle.open_usd:,.2f} "
                    f"Close=${candle.close_usd:,.2f}"
                )


if __name__ == "__main__":
    main()
