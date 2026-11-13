
from dataclasses import dataclass
import math
import time

from prediction_desk.spot_collector import (
    collect_spot_trades,
)


@dataclass(frozen=True)
class PollingSummary:
    cycles_completed: int
    total_fetched: int
    total_inserted: int
    total_duplicates: int
    api_errors: int
    stopped_early: bool


def run_spot_polling(
    client,
    storage,
    assets=("BTC", "ETH"),
    limit=100,
    interval_seconds=5.0,
    max_cycles=3,
    sleep_fn=time.sleep,
    on_cycle=None,
):
    if (
        isinstance(interval_seconds, bool)
        or not isinstance(interval_seconds, (int, float))
        or not math.isfinite(interval_seconds)
        or interval_seconds <= 0
    ):
        raise ValueError("Invalid polling interval")

    if (
        not isinstance(max_cycles, int)
        or isinstance(max_cycles, bool)
        or max_cycles <= 0
    ):
        raise ValueError("Invalid cycle count")

    if not callable(sleep_fn):
        raise TypeError("sleep_fn must be callable")

    if on_cycle is not None and not callable(on_cycle):
        raise TypeError("on_cycle must be callable")

    cycles_completed = 0
    total_fetched = 0
    total_inserted = 0
    total_duplicates = 0
    api_errors = 0
    stopped_early = False

    try:
        for cycle_number in range(1, max_cycles + 1):
            results = collect_spot_trades(
                client=client,
                storage=storage,
                assets=assets,
                limit=limit,
            )

            cycles_completed += 1

            for result in results:
                total_fetched += result.fetched
                total_inserted += result.inserted
                total_duplicates += result.duplicate_count

                if result.status == "api_error":
                    api_errors += 1

            if on_cycle is not None:
                on_cycle(cycle_number, results)

            if cycle_number < max_cycles:
                sleep_fn(interval_seconds)

    except KeyboardInterrupt:
        stopped_early = True

    return PollingSummary(
        cycles_completed=cycles_completed,
        total_fetched=total_fetched,
        total_inserted=total_inserted,
        total_duplicates=total_duplicates,
        api_errors=api_errors,
        stopped_early=stopped_early,
    )
