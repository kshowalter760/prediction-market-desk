
from prediction_desk.spot import (
    CoinbaseSpotClient,
    SpotAPIError,
)


def main():
    print("\nExternal spot-market data")

    with CoinbaseSpotClient() as client:
        for asset in ("BTC", "ETH"):
            try:
                quote = client.get_spot_quote(asset)

            except SpotAPIError as exc:
                print(f"{asset}: {exc}")
                continue

            print(
                f"{quote.product_id}: "
                f"${quote.price_usd:,.2f}"
            )


if __name__ == "__main__":
    main()
