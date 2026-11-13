
import sqlite3

DATABASE = "data/prediction_markets.db"

query = """
SELECT
    o.market_id,
    o.outcome_name,
    COUNT(*) AS level_updates
FROM market_level_updates AS l
JOIN outcomes AS o
    ON l.token_id = o.token_id
GROUP BY
    o.market_id,
    o.outcome_name
ORDER BY
    o.market_id,
    o.outcome_name
"""

with sqlite3.connect(DATABASE) as connection:
    results = connection.execute(query).fetchall()

print("\nMARKET OUTCOME VALIDATION")
print("=" * 45)

if not results:
    print("No matching registered outcomes found.")
else:
    for market_id, outcome_name, count in results:
        print(
            f"Market: {market_id} | "
            f"Outcome: {outcome_name} | "
            f"Updates: {count}"
        )
