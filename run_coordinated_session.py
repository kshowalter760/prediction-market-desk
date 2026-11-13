
import argparse

from prediction_desk.coordinator import (
    run_coordinated_session,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Coordinated Coinbase and "
            "Polymarket live collection"
        )
    )

    parser.add_argument(
        "--token-id",
        action="append",
        required=True,
        help=(
            "Polymarket outcome token ID; "
            "repeat for each token"
        ),
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=30,
        help="Collection duration in seconds",
    )

    parser.add_argument(
        "--database",
        default="data/prediction_markets.db",
        help="SQLite database path",
    )

    args = parser.parse_args()

    print("\nCoordinated market collection")
    print(f"Polymarket tokens: {len(args.token_id)}")
    print(f"Requested duration: {args.duration} seconds")

    result = run_coordinated_session(
        database_path=args.database,
        token_ids=args.token_id,
        duration_seconds=args.duration,
    )

    print("\nSession summary")
    print(f"Started: {result.started_at_utc}")
    print(f"Completed: {result.completed_at_utc}")
    print(f"Elapsed: {result.duration_seconds:.2f}s")

    for worker in (
        result.coinbase,
        result.polymarket,
    ):
        print(f"\n{worker.name.upper()}")
        print(f"Worker status: {worker.status}")

        if worker.error:
            print(f"Error: {worker.error}")

        elif worker.result is not None:
            for field, value in vars(
                worker.result
            ).items():
                print(f"{field}: {value}")


if __name__ == "__main__":
    main()
