
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class BookLevel:
    side: str
    price: Decimal
    size: Decimal


def parse_book_depth(message: dict) -> list[BookLevel]:
    if not isinstance(message, dict):
        raise ValueError("Book message must be a dictionary")

    levels = []

    for source_key, side in (
        ("bids", "BUY"),
        ("asks", "SELL"),
    ):
        raw_levels = message.get(source_key)

        if not isinstance(raw_levels, list):
            raise ValueError(
                f"Missing or invalid {source_key} levels"
            )

        for raw_level in raw_levels:
            if not isinstance(raw_level, dict):
                raise ValueError("Invalid book level")

            try:
                price = Decimal(str(raw_level["price"]))
                size = Decimal(str(raw_level["size"]))
            except (
                KeyError,
                TypeError,
                InvalidOperation,
            ) as exc:
                raise ValueError(
                    "Invalid book level values"
                ) from exc

            if not price.is_finite() or not (
                Decimal("0") < price < Decimal("1")
            ):
                raise ValueError(
                    "Book level price must be between 0 and 1"
                )

            if not size.is_finite() or size < 0:
                raise ValueError(
                    "Book level size must be nonnegative"
                )

            levels.append(
                BookLevel(
                    side=side,
                    price=price,
                    size=size,
                )
            )

    return levels
