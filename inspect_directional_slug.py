
from datetime import datetime, timedelta, timezone

import httpx


GAMMA_URL = "https://gamma-api.polymarket.com"

INTERVAL_SECONDS = 15 * 60


def main():
    now = datetime.now(timezone.utc)

    current_bucket = (
        int(now.timestamp()) // INTERVAL_SECONDS
    ) * INTERVAL_SECONDS

    buckets = [
        current_bucket,
        current_bucket + INTERVAL_SECONDS,
        current_bucket + 2 * INTERVAL_SECONDS,
    ]

    with httpx.Client(timeout=15.0) as client:
        for asset in ("btc", "eth"):
            for timestamp in buckets:
                slug = f"{asset}-updown-15m-{timestamp}"

                response = client.get(
                    f"{GAMMA_URL}/events/slug/{slug}"
                )

                print(f"\nSlug: {slug}")
                print(f"HTTP status: {response.status_code}")

                if response.status_code == 404:
                    continue

                response.raise_for_status()

                event = response.json()

                print("Title:", event.get("title"))
                print("Active:", event.get("active"))
                print("Closed:", event.get("closed"))

                for market in event.get("markets", []):
                    print(
                        "Market:",
                        market.get("question"),
                    )
                    print(
                        "Accepting orders:",
                        market.get("acceptingOrders"),
                    )
                    print(
                        "End date:",
                        market.get("endDate"),
                    )


if __name__ == "__main__":
    main()
