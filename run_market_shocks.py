
from decimal import Decimal
from pathlib import Path

from prediction_desk.market_signals import (
    consolidate_market_shocks,
)
from prediction_desk.signals import detect_price_shocks
from prediction_desk.storage import Storage


DATABASE_PATH = Path("data/prediction_markets.db")


def main():
    all_shocks = []

    with Storage(DATABASE_PATH) as storage:
        storage.initialize()

        tokens = storage.connection.execute(
            """
            SELECT token_id
            FROM outcomes
            """
        ).fetchall()

        for (token_id,) in tokens:
            history = storage.get_outcome_history(
                token_id,
                limit=100,
            )

            shocks = detect_price_shocks(
                history,
                threshold=Decimal("0.10"),
                max_spread=Decimal("0.03"),
                max_gap_seconds=60,
                require_fresh=True,
            )

            all_shocks.extend(shocks)

    events = consolidate_market_shocks(
        all_shocks,
        tolerance_ms=2000,
    )

    print(
        f"\nOutcome-level shocks: "
        f"{len(all_shocks)}"
    )
    print(
        f"Market-level events: "
        f"{len(events)}"
    )

    for event in events:
        print(
            f"\nMarket ID: {event.market_id}"
        )
        print(
            f"Magnitude: "
            f"{event.magnitude * 100} "
            f"percentage points"
        )
        print(
            f"Supporting outcomes: "
            f"{len(event.outcome_shocks)}"
        )

        for shock in event.outcome_shocks:
            print(
                f"  {shock.outcome_name}: "
                f"{shock.change * 100:+} pp"
            )


if __name__ == "__main__":
    main()
