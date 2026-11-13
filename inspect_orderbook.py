
import json

import httpx


GAMMA_URL = "https://gamma-api.polymarket.com"
CLOB_URL = "https://clob.polymarket.com"


def main():
    with httpx.Client(timeout=15.0) as client:
        try:
            response = client.get(
                f"{GAMMA_URL}/markets",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": 20,
                },
            )
            response.raise_for_status()
            markets = response.json()

            for market in markets:
                if not market.get("enableOrderBook"):
                    continue

                token_ids = json.loads(
                    market["clobTokenIds"]
                )

                if not token_ids:
                    continue

                token_id = token_ids[0]

                book_response = client.get(
                    f"{CLOB_URL}/book",
                    params={"token_id": token_id},
                )
                book_response.raise_for_status()
                book = book_response.json()

                print("MARKET:")
                print(market["question"])

                print("\nTOKEN ID:")
                print(token_id)

                print("\nORDER BOOK SUMMARY:")

                from decimal import Decimal

                bids = book.get("bids", [])
                asks = book.get("asks", [])

                print(f"Bid levels: {len(bids)}")
                print(f"Ask levels: {len(asks)}")

                if bids and asks:
                    best_bid = max(
                        Decimal(level["price"])
                        for level in bids
                    )

                    best_ask = min(
                        Decimal(level["price"])
                        for level in asks
                    )

                    spread = best_ask - best_bid

                    print(f"Best bid: {best_bid}")
                    print(f"Best ask: {best_ask}")
                    print(f"Spread: {spread}")
                    print(f"Spread (percentage points): {spread * 100}")
                else:
                    print("Incomplete order book")

                return

            print("No eligible market found.")

        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            TypeError,
        ) as exc:
            print(f"Inspection failed: {exc}")


if __name__ == "__main__":
    main()
