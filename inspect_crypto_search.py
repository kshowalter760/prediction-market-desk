
import httpx


SEARCH_URL = "https://gamma-api.polymarket.com/public-search"


def main():
    queries = ["Bitcoin", "Ethereum"]

    with httpx.Client(timeout=15.0) as client:
        for query in queries:
            print(f"\nSearching for: {query}")

            response = client.get(
                SEARCH_URL,
                params={
                    "q": query,
                    "limit_per_type": 10,
                },
            )
            response.raise_for_status()

            data = response.json()

            print("Response keys:", list(data.keys()))

            events = data.get("events", [])

            print("Events returned:", len(events))

            for event in events[:10]:
                print(
                    "-",
                    event.get("title"),
                    "| Markets:",
                    len(event.get("markets", [])),
                )


if __name__ == "__main__":
    main()
