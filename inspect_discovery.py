
from prediction_desk.discovery import (
    discover_crypto_markets,
)
from prediction_desk.polymarket import PolymarketClient


def main():
    with PolymarketClient() as client:
        candidates = discover_crypto_markets(
            client=client,
            page_size=100,
            max_pages=5,
        )

    print(f"Discovered {len(candidates)} candidates")

    for candidate in candidates[:30]:
        print(
            f"[{candidate.asset}] "
            f"{candidate.market_id}: "
            f"{candidate.question}"
        )


if __name__ == "__main__":
    main()
