
from decimal import Decimal
from pathlib import Path

from prediction_desk.market_signals import (
    consolidate_market_shocks,
)
from prediction_desk.signals import detect_price_shocks
from prediction_desk.storage import Storage


DATABASE_PATH = Path("data/prediction_markets.db")


def main():
    with Storage(DATABASE_PATH) as storage:
        storage.initialize()

        tokens = storage.connection.execute(
            """
            SELECT token_id
            FROM outcomes
            """
        ).fetchall()

        all_shocks = []

        for (token_id,) in tokens:
            history = storage.get_outcome_history(
                token_id,
                limit=100,
            )

            all_shocks.extend(
                detect_price_shocks(
                    history,
                    threshold=Decimal("0.10"),
                    max_spread=Decimal("0.03"),
                    max_gap_seconds=60,
                    require_fresh=True,
                )
            )

        events = consolidate_market_shocks(
            all_shocks,
            tolerance_ms=2000,
        )

        inserted = 0
        duplicates = 0

        for event in events:
            if storage.save_market_shock(event):
                inserted += 1
            else:
                duplicates += 1

        print("\nResearch event persistence")
        print(f"Outcome shocks: {len(all_shocks)}")
        print(f"Market events: {len(events)}")
        print(f"New events saved: {inserted}")
        print(f"Duplicates skipped: {duplicates}")
        print(
            f"Total stored market events: "
            f"{storage.count_market_shocks()}"
        )


if __name__ == "__main__":
    main()
