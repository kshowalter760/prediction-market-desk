
import time

import httpx


GAMMA_URL = "https://gamma-api.polymarket.com"
CLOB_URL = "https://clob.polymarket.com"

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class PolymarketAPIError(Exception):
    """Raised when a Polymarket API request fails."""


class PolymarketClient:
    def __init__(
        self,
        timeout_seconds=15.0,
        max_retries=2,
        retry_delay_seconds=1.0,
        transport=None,
    ):
        if timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")

        if not isinstance(max_retries, int) or max_retries < 0:
            raise ValueError("max_retries must be nonnegative")

        if retry_delay_seconds < 0:
            raise ValueError("Retry delay must be nonnegative")

        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

        self.client = httpx.Client(
            timeout=timeout_seconds,
            transport=transport,
        )

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def _get(self, url, params=None):
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.get(
                    url,
                    params=params,
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code

                if (
                    status_code not in RETRYABLE_STATUS_CODES
                    or attempt == self.max_retries
                ):
                    raise PolymarketAPIError(
                        f"HTTP {status_code}: {url}"
                    ) from exc

            except (
                httpx.RequestError,
                ValueError,
            ) as exc:
                if attempt == self.max_retries:
                    raise PolymarketAPIError(
                        f"Request failed: {url}"
                    ) from exc

            time.sleep(
                self.retry_delay_seconds * (2 ** attempt)
            )

        raise PolymarketAPIError("Retry attempts exhausted")

    def get_markets(self, limit=100, offset=0):
        if not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")

        if not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be nonnegative")

        data = self._get(
            f"{GAMMA_URL}/markets",
            params={
                "active": "true",
                "closed": "false",
                "limit": limit,
                "offset": offset,
            },
        )

        if not isinstance(data, list):
            raise PolymarketAPIError(
                "Unexpected Gamma response structure"
            )

        return data


    def search_events(self, query, limit=20, page=1):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be nonempty")

        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 100
        ):
            raise ValueError("limit must be between 1 and 100")

        if (
            not isinstance(page, int)
            or isinstance(page, bool)
            or page < 1
        ):
            raise ValueError("page must be positive")

        data = self._get(
            f"{GAMMA_URL}/public-search",
            params={
                "q": query.strip(),
                "limit_per_type": limit,
                "page": page,
                "keep_closed_markets": 0,
            },
        )

        if not isinstance(data, dict):
            raise PolymarketAPIError(
                "Unexpected search response"
            )

        if not isinstance(data.get("events"), list):
            raise PolymarketAPIError(
                "Search response missing events"
            )

        return data


    def get_event_by_slug(self, slug):
        if not isinstance(slug, str) or not slug.strip():
            raise ValueError("slug must be nonempty")

        try:
            data = self._get(
                f"{GAMMA_URL}/events/slug/{slug}"
            )
        except PolymarketAPIError as exc:
            if "HTTP 404:" in str(exc):
                return None
            raise

        if not isinstance(data, dict):
            raise PolymarketAPIError(
                "Unexpected event response structure"
            )

        return data



    def get_order_book(self, token_id):
        token_id = str(token_id)

        if not token_id.isdigit():
            raise ValueError("Invalid token ID")

        data = self._get(
            f"{CLOB_URL}/book",
            params={"token_id": token_id},
        )

        if not isinstance(data, dict):
            raise PolymarketAPIError(
                "Unexpected CLOB response structure"
            )

        if str(data.get("asset_id")) != token_id:
            raise PolymarketAPIError(
                "Order-book token ID mismatch"
            )

        return data
