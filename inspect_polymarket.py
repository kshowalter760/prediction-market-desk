
import json

import httpx


BASE_URL = "https://gamma-api.polymarket.com"


def main():
    params = {
        "active": "true",
        "closed": "false",
        "limit": 5,
        "offset": 0,
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(
                f"{BASE_URL}/markets",
                params=params,
            )
            response.raise_for_status()
            markets = response.json()

    except httpx.HTTPError as exc:
        print(f"API request failed: {exc}")
        return

    except ValueError as exc:
        print(f"Invalid JSON response: {exc}")
        return

    if not isinstance(markets, list):
        print("Unexpected response structure")
        return

    print(f"Markets returned: {len(markets)}")

    if not markets:
        return

    market = markets[0]

    fields = [
        "id",
        "question",
        "conditionId",
        "active",
        "closed",
        "endDate",
        "outcomes",
        "outcomePrices",
        "clobTokenIds",
        "volume",
        "liquidity",
        "enableOrderBook",
    ]

    for field in fields:
        print(f"\n{field}:")
        print(json.dumps(market.get(field), indent=2))


if __name__ == "__main__":
    main()
