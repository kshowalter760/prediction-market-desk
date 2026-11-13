
from collections import Counter
from datetime import datetime, timezone

from prediction_desk.polymarket import PolymarketClient


def main():
    rejection_reasons = Counter()
    examples = []
    total_directional = 0

    now = datetime.now(timezone.utc)

    with PolymarketClient() as client:
        for query in ("Bitcoin Up or Down", "Ethereum Up or Down"):
            response = client.search_events(
                query=query,
                limit=30,
                page=1,
            )

            for event in response["events"]:
                title = event.get("title", "")

                if "up or down" not in title.lower():
                    continue

                for market in event.get("markets", []):
                    total_directional += 1
                    reasons = []

                    if market.get("active") is not True:
                        reasons.append("inactive")

                    if market.get("closed") is not False:
                        reasons.append("closed")

                    if market.get("acceptingOrders") is not True:
                        reasons.append("not_accepting_orders")

                    if market.get("enableOrderBook") is not True:
                        reasons.append("no_order_book")

                    end_date = market.get("endDate")

                    try:
                        expiry = datetime.fromisoformat(
                            end_date.replace("Z", "+00:00")
                        )
                        if expiry <= now:
                            reasons.append("expired")
                    except (AttributeError, ValueError, TypeError):
                        reasons.append("invalid_expiry")

                    if not reasons:
                        rejection_reasons["eligible"] += 1
                    else:
                        for reason in reasons:
                            rejection_reasons[reason] += 1

                    if len(examples) < 12:
                        examples.append({
                            "title": title,
                            "end_date": end_date,
                            "reasons": reasons or ["eligible"],
                        })

    print(f"\nDirectional contracts inspected: {total_directional}")

    print("\nEligibility diagnostics:")
    for reason, count in rejection_reasons.most_common():
        print(f"  {reason}: {count}")

    print("\nExamples:")
    for example in examples:
        print(f"\n{example['title']}")
        print(f"  Expires: {example['end_date']}")
        print(f"  Status: {', '.join(example['reasons'])}")


if __name__ == "__main__":
    main()
