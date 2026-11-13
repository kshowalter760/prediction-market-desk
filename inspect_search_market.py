
import json

import httpx


SEARCH_URL = "https://gamma-api.polymarket.com/public-search"


def main():
    with httpx.Client(timeout=15.0) as client:
        response = client.get(
            SEARCH_URL,
            params={
                "q": "Bitcoin",
                "limit_per_type": 10,
            },
        )
        response.raise_for_status()
        data = response.json()

    for event in data.get("events", []):
        markets = event.get("markets", [])

        if not markets:
            continue

        market = markets[0]

        fields = [
            "id",
            "question",
            "conditionId",
            "active",
            "closed",
            "endDate",
            "enableOrderBook",
            "acceptingOrders",
            "clobTokenIds",
            "outcomes",
            "outcomePrices",
        ]

        print("EVENT TITLE:", event.get("title"))
        print("EVENT ACTIVE:", event.get("active"))
        print("EVENT CLOSED:", event.get("closed"))
        print()

        for field in fields:
            value = market.get(field)
            print(
                f"{field}: {str(value)[:200]} "
                f"(type={type(value).__name__})"
            )

        print("\nEVENT MARKET COUNT:", len(markets))
        print("\nPAGINATION:")
        print(json.dumps(data.get("pagination"), indent=2))

        break


if __name__ == "__main__":
    main()
