
import sqlite3
from datetime import datetime, timezone

DATABASE = "data/prediction_markets.db"


def main():
    now = datetime.now(timezone.utc)

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    try:
        rows = connection.execute(
            """
            SELECT
                m.market_id,
                m.event_title,
                m.asset,
                m.end_date,
                o.outcome_name,
                o.token_id
            FROM markets AS m
            JOIN outcomes AS o
                ON o.market_id = m.market_id
            WHERE m.asset = 'BTC'
              AND m.market_type = 'directional'
            ORDER BY m.end_date DESC, o.outcome_name
            """
        ).fetchall()

        active = {}

        for row in rows:
            end_date = row["end_date"]

            if not end_date:
                continue

            try:
                expiry = datetime.fromisoformat(
                    end_date.replace("Z", "+00:00")
                )
            except ValueError:
                continue

            if expiry.tzinfo is None:
                continue

            if expiry <= now:
                continue

            market_id = row["market_id"]

            active.setdefault(
                market_id,
                {
                    "title": row["event_title"],
                    "end_date": end_date,
                    "tokens": {},
                },
            )

            active[market_id]["tokens"][
                row["outcome_name"]
            ] = row["token_id"]

        print("\nFUTURE-EXPIRING BTC DIRECTIONAL MARKETS")
        print("=" * 60)

        for market_id, market in active.items():
            print(f"\nMarket ID: {market_id}")
            print(f"Title: {market['title']}")
            print(f"Expires: {market['end_date']}")

            for outcome, token in market["tokens"].items():
                print(f"{outcome}: {token}")

        print(f"\nMarkets found: {len(active)}")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
