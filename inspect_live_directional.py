
from prediction_desk.discovery import (
    discover_directional_markets,
)
from prediction_desk.polymarket import PolymarketClient


def main():
    with PolymarketClient() as client:
        markets = discover_directional_markets(
            client,
            future_intervals=2,
        )

    print(f"\nDirectional markets: {len(markets)}")

    for market in markets:
        print(
            f"\n[{market.asset}] "
            f"{market.question}"
        )
        print(f"Market ID: {market.market_id}")
        print(f"Expires: {market.end_date}")

        for outcome, token_id in market.outcome_tokens:
            print(
                f"  {outcome}: {token_id}"
            )


if __name__ == "__main__":
    main()
