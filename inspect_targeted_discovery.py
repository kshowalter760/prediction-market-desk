
from collections import Counter

from prediction_desk.discovery import (
    discover_targeted_markets,
)
from prediction_desk.polymarket import PolymarketClient


def main():
    with PolymarketClient() as client:
        markets = discover_targeted_markets(
            client,
            limit=20,
            max_pages=3,
        )

    print(f"\nTradable candidates: {len(markets)}")
    print(
        "By asset:",
        dict(Counter(m.asset for m in markets)),
    )
    print(
        "By type:",
        dict(Counter(m.market_type for m in markets)),
    )

    for market in markets[:25]:
        print(
            f"[{market.asset}] "
            f"[{market.market_type}] "
            f"{market.question}"
        )


if __name__ == "__main__":
    main()
