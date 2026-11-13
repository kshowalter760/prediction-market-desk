
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DATABASE_PATH = Path("data/prediction_markets.db")


def main():
    now = datetime.now(timezone.utc)

    with sqlite3.connect(DATABASE_PATH) as connection:
        rows = connection.execute(
            """
            SELECT
                m.market_id,
                m.question,
                m.end_date,
                o.outcome_name,
                o.token_id
            FROM markets AS m
            JOIN outcomes AS o
                ON o.market_id = m.market_id
            WHERE m.market_type = 'directional'
              AND m.end_date > ?
            ORDER BY m.end_date ASC, m.market_id
            """,
            (now.isoformat().replace("+00:00", "Z"),),
        ).fetchall()

    markets = {}

    for market_id, question, end_date, outcome, token_id in rows:
        market = markets.setdefault(
            market_id,
            {
                "question": question,
                "end_date": end_date,
                "tokens": {},
            },
        )
        market["tokens"][outcome.lower()] = token_id

    if not markets:
        print("No unexpired directional markets in the registry.")
        print("Run: python run_market_registry.py")
        return

    for market_id, market in markets.items():
        if not {"up", "down"}.issubset(market["tokens"]):
            continue

        print(f"\nMarket ID: {market_id}")
        print(f"Question: {market['question']}")
        print(f"End date: {market['end_date']}")
        print(f"UP token: {market['tokens']['up']}")
        print(f"DOWN token: {market['tokens']['down']}")

        print("\nCapture command:")
        print(
            "python run_coordinated_session.py "
            f"--token-id {market['tokens']['up']} "
            f"--token-id {market['tokens']['down']} "
            "--duration 90"
        )


if __name__ == "__main__":
    main()

