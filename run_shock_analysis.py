
from decimal import Decimal
from pathlib import Path

from prediction_desk.signals import detect_price_shocks
from prediction_desk.storage import Storage


DATABASE_PATH = Path("data/prediction_markets.db")


def main():
    with Storage(DATABASE_PATH) as storage:
        storage.initialize()

        tokens = storage.connection.execute(
            """
            SELECT
                o.token_id,
                m.asset,
                o.outcome_name,
                m.question
            FROM outcomes AS o
            JOIN markets AS m
                ON o.market_id = m.market_id
            ORDER BY m.end_date DESC
            """
        ).fetchall()

        total_shocks = 0

        for token_id, asset, outcome_name, question in tokens:
            history = storage.get_outcome_history(
                token_id,
                limit=100,
            )

            shocks = detect_price_shocks(
                history,
                threshold=Decimal("0.10"),
                max_spread=Decimal("0.03"),
                require_fresh=True,
            )

            for shock in shocks:
                total_shocks += 1

                print(f"\n[{asset}] {outcome_name}")
                print(f"Market: {question}")
                print(
                    f"Midpoint: "
                    f"{shock.previous_midpoint} -> "
                    f"{shock.current_midpoint}"
                )
                print(
                    f"Change: "
                    f"{shock.change * 100:+} "
                    f"percentage points"
                )
                print(
                    f"Time: "
                    f"{shock.previous_timestamp_ms} -> "
                    f"{shock.current_timestamp_ms}"
                )

        print(f"\nTotal detected shocks: {total_shocks}")


if __name__ == "__main__":
    main()
