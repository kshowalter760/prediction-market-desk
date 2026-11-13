
from dataclasses import dataclass

from prediction_desk.polymarket import PolymarketAPIError
from prediction_desk.scanner import ingest_order_book


@dataclass(frozen=True)
class ObservationResult:
    markets_processed: int
    tokens_attempted: int
    snapshots_inserted: int
    snapshots_duplicate: int
    failures: tuple[str, ...]


def observe_markets(client, storage, markets):
    tokens_attempted = 0
    snapshots_inserted = 0
    snapshots_duplicate = 0
    failures = []

    for market in markets:
        storage.save_market(market)

        for outcome_name, token_id in market.outcome_tokens:
            tokens_attempted += 1

            try:
                result = ingest_order_book(
                    client=client,
                    storage=storage,
                    token_id=token_id,
                )

            except (PolymarketAPIError, ValueError) as exc:
                failures.append(
                    f"Market {market.market_id}, "
                    f"{outcome_name}: {exc}"
                )
                continue

            if result["inserted"]:
                snapshots_inserted += 1
            else:
                snapshots_duplicate += 1

    return ObservationResult(
        markets_processed=len(markets),
        tokens_attempted=tokens_attempted,
        snapshots_inserted=snapshots_inserted,
        snapshots_duplicate=snapshots_duplicate,
        failures=tuple(failures),
    )
