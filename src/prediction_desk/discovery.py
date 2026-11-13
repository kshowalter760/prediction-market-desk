import json
from datetime import datetime, timezone
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TradableCryptoMarket:
    market_id: str
    event_title: str
    question: str
    asset: str
    market_type: str
    condition_id: str
    end_date: str
    outcome_tokens: tuple[tuple[str, str], ...]


def decode_string_list(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None

    if not isinstance(value, list):
        return None

    if not value or not all(
        isinstance(item, str) and item
        for item in value
    ):
        return None

    return value


def normalize_crypto_market(event, market, now=None):
    if not isinstance(event, dict):
        return None

    if not isinstance(market, dict):
        return None

    if now is None:
        now = datetime.now(timezone.utc)

    if market.get("active") is not True:
        return None

    if market.get("closed") is not False:
        return None

    if market.get("acceptingOrders") is not True:
        return None

    if market.get("enableOrderBook") is not True:
        return None

    end_date = market.get("endDate")

    if not isinstance(end_date, str):
        return None

    try:
        expires_at = datetime.fromisoformat(
            end_date.replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if expires_at.tzinfo is None:
        return None

    if expires_at <= now:
        return None

    question = market.get("question")
    event_title = event.get("title")

    if not isinstance(question, str):
        return None

    if not isinstance(event_title, str):
        return None

    combined_text = f"{event_title} {question}"

    matched_assets = [
        asset
        for asset, pattern in ASSET_PATTERNS.items()
        if pattern.search(combined_text)
    ]

    if len(matched_assets) != 1:
        return None

    asset = matched_assets[0]

    if re.search(
        r"\bup or down\b",
        combined_text,
        re.IGNORECASE,
    ):
        market_type = "directional"
    elif PRICE_TERMS.search(combined_text):
        market_type = "price_target"
    else:
        return None

    outcomes = decode_string_list(
        market.get("outcomes")
    )

    token_ids = decode_string_list(
        market.get("clobTokenIds")
    )

    if outcomes is None or token_ids is None:
        return None

    if len(outcomes) != len(token_ids):
        return None

    if len(set(token_ids)) != len(token_ids):
        return None

    if not all(token.isdigit() for token in token_ids):
        return None

    market_id = market.get("id")
    condition_id = market.get("conditionId")

    if not market_id or not condition_id:
        return None

    return TradableCryptoMarket(
        market_id=str(market_id),
        event_title=event_title,
        question=question,
        asset=asset,
        market_type=market_type,
        condition_id=str(condition_id),
        end_date=end_date,
        outcome_tokens=tuple(
            zip(outcomes, token_ids)
        ),
    )


def discover_targeted_markets(
    client,
    limit=20,
    max_pages=3,
):
    results = []
    seen_ids = set()

    for query in ("Bitcoin", "Ethereum"):
        for page in range(1, max_pages + 1):
            response = client.search_events(
                query=query,
                limit=limit,
                page=page,
            )

            events = response["events"]

            for event in events:
                if not isinstance(event, dict):
                    continue

                markets = event.get("markets", [])

                if not isinstance(markets, list):
                    continue

                for market in markets:
                    candidate = normalize_crypto_market(
                        event,
                        market,
                    )

                    if candidate is None:
                        continue

                    if candidate.market_id in seen_ids:
                        continue

                    seen_ids.add(candidate.market_id)
                    results.append(candidate)

            pagination = response.get("pagination", {})

            if not isinstance(pagination, dict):
                break

            if pagination.get("hasMore") is not True:
                break

    return results



ASSET_PATTERNS = {
    "BTC": re.compile(
        r"\b(?:BTC|Bitcoin)\b",
        re.IGNORECASE,
    ),
    "ETH": re.compile(
        r"\b(?:ETH|Ethereum)\b",
        re.IGNORECASE,
    ),
}

PRICE_TERMS = re.compile(
    r"\b(?:price|above|below|over|under|reach|hit|"
    r"higher|lower|between|up or down)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MarketCandidate:
    market_id: str
    question: str
    asset: str
    condition_id: str
    end_date: str | None


def classify_market(market: dict):
    if not isinstance(market, dict):
        return None

    if market.get("active") is not True:
        return None

    if market.get("closed") is not False:
        return None

    question = market.get("question")

    if not isinstance(question, str):
        return None

    if not PRICE_TERMS.search(question):
        return None

    matched_assets = [
        asset
        for asset, pattern in ASSET_PATTERNS.items()
        if pattern.search(question)
    ]

    if len(matched_assets) != 1:
        return None

    market_id = market.get("id")
    condition_id = market.get("conditionId")

    if not market_id or not condition_id:
        return None

    return MarketCandidate(
        market_id=str(market_id),
        question=question,
        asset=matched_assets[0],
        condition_id=str(condition_id),
        end_date=market.get("endDate"),
    )


def discover_crypto_markets(
    client,
    page_size=100,
    max_pages=5,
):
    if (
        not isinstance(page_size, int)
        or isinstance(page_size, bool)
        or not 1 <= page_size <= 500
    ):
        raise ValueError(
            "page_size must be between 1 and 500"
        )

    if (
        not isinstance(max_pages, int)
        or isinstance(max_pages, bool)
        or max_pages <= 0
    ):
        raise ValueError(
            "max_pages must be positive"
        )

    candidates = []
    seen_market_ids = set()

    for page in range(max_pages):
        markets = client.get_markets(
            limit=page_size,
            offset=page * page_size,
        )

        for market in markets:
            candidate = classify_market(market)

            if candidate is None:
                continue

            if candidate.market_id in seen_market_ids:
                continue

            seen_market_ids.add(candidate.market_id)
            candidates.append(candidate)

        if len(markets) < page_size:
            break

    return candidates


def discover_directional_markets(
    client,
    now=None,
    future_intervals=2,
):
    if now is None:
        now = datetime.now(timezone.utc)

    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    if (
        not isinstance(future_intervals, int)
        or isinstance(future_intervals, bool)
        or future_intervals < 0
    ):
        raise ValueError(
            "future_intervals must be nonnegative"
        )

    interval_seconds = 15 * 60

    current_bucket = (
        int(now.timestamp()) // interval_seconds
    ) * interval_seconds

    results = []
    seen_market_ids = set()

    for asset in ("btc", "eth"):
        for index in range(future_intervals + 1):
            timestamp = (
                current_bucket
                + index * interval_seconds
            )

            slug = (
                f"{asset}-updown-15m-{timestamp}"
            )

            event = client.get_event_by_slug(slug)

            if event is None:
                continue

            markets = event.get("markets", [])

            if not isinstance(markets, list):
                continue

            for market in markets:
                candidate = normalize_crypto_market(
                    event,
                    market,
                    now=now,
                )

                if candidate is None:
                    continue

                if candidate.market_type != "directional":
                    continue

                if candidate.market_id in seen_market_ids:
                    continue

                seen_market_ids.add(candidate.market_id)
                results.append(candidate)

    return results
