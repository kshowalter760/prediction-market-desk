
from pathlib import Path

from prediction_desk.storage import Storage


DATABASE_PATH = Path("data/prediction_markets.db")


def main():
    with Storage(DATABASE_PATH) as storage:
        storage.initialize()

        token = storage.connection.execute(
            """
            SELECT
                o.token_id,
                o.outcome_name,
                m.asset,
                m.question
            FROM outcomes AS o
            JOIN markets AS m
                ON o.market_id = m.market_id
            WHERE m.market_type = 'directional'
            ORDER BY m.end_date DESC
            LIMIT 1
            """
        ).fetchone()

        if token is None:
            print("No directional outcomes found")
            return

        token_id, outcome_name, asset, question = token

        print(f"\nAsset: {asset}")
        print(f"Market: {question}")
        print(f"Outcome: {outcome_name}")

        history = storage.get_outcome_history(
            token_id,
            limit=10,
        )

        print(f"Historical observations: {len(history)}")

        for row in history:
            print(
                f"\nTimestamp: "
                f"{row['source_timestamp_ms']}"
            )
            print(f"Bid: {row['best_bid']}")
            print(f"Ask: {row['best_ask']}")
            print(f"Spread: {row['spread']}")


if __name__ == "__main__":
    main()
