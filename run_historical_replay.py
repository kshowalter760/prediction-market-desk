
import argparse
import sqlite3
from pathlib import Path

from prediction_desk.historical_replay import (
    replay_from_snapshot,
)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--database",
        default="data/prediction_markets.db",
    )

    parser.add_argument(
        "--snapshot-id",
        type=int,
        action="append",
        required=True,
    )

    args = parser.parse_args()
    database = Path(args.database)

    if not database.is_file():
        raise FileNotFoundError(
            f"Database not found: {database.resolve()}"
        )

    with sqlite3.connect(database) as connection:
        for snapshot_id in args.snapshot_id:
            result = replay_from_snapshot(
                connection,
                snapshot_id,
            )

            initial = result.initial_state
            final = result.final_state

            print()
            print(f"SNAPSHOT {snapshot_id} — HISTORICAL REPLAY")
            print("=" * 60)
            print(f"Token: {result.token_id}")
            print(f"Updates applied: {result.updates_applied}")
            print(f"First update: {result.first_update_ms}")
            print(f"Last update: {result.last_update_ms}")
            print()
            print(f"Initial best bid: {initial.best_bid}")
            print(f"Final best bid:   {final.best_bid}")
            print(f"Initial best ask: {initial.best_ask}")
            print(f"Final best ask:   {final.best_ask}")
            print(f"Initial spread:   {initial.spread}")
            print(f"Final spread:     {final.spread}")
            print(f"Final bid depth:  {final.bid_depth}")
            print(f"Final ask depth:  {final.ask_depth}")
            print(f"Final imbalance:  {final.imbalance}")
            print()
            print(
                "Continuity verified:",
                result.continuity_verified,
            )
            print(
                "Absolute-size semantics verified:",
                result.absolute_size_semantics_verified,
            )


if __name__ == "__main__":
    main()
