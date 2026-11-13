
import csv
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


EXPECTED_COLUMNS = (
    "token_id",
    "session_id",
    "timestamp_ms",
    "message_sequence",
    "alignment_status",
    "spot_price_usd",
    "spot_age_ms",
    "spot_return_pct",
    "polymarket_mid_price",
    "polymarket_mid_change",
    "polymarket_spread",
    "polymarket_imbalance",
)

ALIGNMENT_STATUSES = {
    "aligned",
    "stale_spot",
    "missing_spot",
}

DECIMAL_COLUMNS = (
    "spot_price_usd",
    "spot_return_pct",
    "polymarket_mid_price",
    "polymarket_mid_change",
    "polymarket_spread",
    "polymarket_imbalance",
)


@dataclass(frozen=True)
class CSVValidationReport:
    path: str
    row_count: int
    token_count: int
    duplicate_count: int
    temporal_violation_count: int
    errors: tuple[str, ...]
    valid: bool


def _parse_integer(value, field, row_number, errors):
    if not value or not value.isascii() or not value.isdecimal():
        errors.append(
            f"Row {row_number}: invalid integer in {field}"
        )
        return None

    try:
        return int(value)
    except ValueError:
        errors.append(
            f"Row {row_number}: invalid integer in {field}"
        )
        return None


def _parse_decimal(value, field, row_number, errors):
    if value == "":
        return None

    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        errors.append(
            f"Row {row_number}: invalid decimal in {field}"
        )
        return None

    if not number.is_finite():
        errors.append(
            f"Row {row_number}: non-finite decimal in {field}"
        )
        return None

    return number


def validate_research_csv(path):
    path = Path(path)
    errors = []
    identities = set()
    previous_by_token = {}
    tokens = set()

    row_count = 0
    duplicate_count = 0
    temporal_violation_count = 0

    with path.open(
        newline="",
        encoding="utf-8-sig",
    ) as file:
        reader = csv.DictReader(file)

        if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
            return CSVValidationReport(
                path=str(path),
                row_count=0,
                token_count=0,
                duplicate_count=0,
                temporal_violation_count=0,
                errors=("CSV schema does not match expected columns",),
                valid=False,
            )

        for row_number, row in enumerate(reader, start=2):
            row_count += 1

            if None in row or any(
                value is None for value in row.values()
            ):
                errors.append(
                    f"Row {row_number}: malformed CSV record"
                )
                continue

            token_id = row["token_id"]
            if not token_id.strip():
                errors.append(
                    f"Row {row_number}: missing token_id"
                )
                continue

            tokens.add(token_id)

            session_id = _parse_integer(
                row["session_id"],
                "session_id",
                row_number,
                errors,
            )
            timestamp_ms = _parse_integer(
                row["timestamp_ms"],
                "timestamp_ms",
                row_number,
                errors,
            )
            sequence = _parse_integer(
                row["message_sequence"],
                "message_sequence",
                row_number,
                errors,
            )

            for field, value in (
                ("session_id", session_id),
                ("timestamp_ms", timestamp_ms),
                ("message_sequence", sequence),
            ):
                if value is not None and value <= 0:
                    errors.append(
                        f"Row {row_number}: {field} must be positive"
                    )

            status = row["alignment_status"]

            if status not in ALIGNMENT_STATUSES:
                errors.append(
                    f"Row {row_number}: invalid alignment_status"
                )

            spot_age = None
            if row["spot_age_ms"] != "":
                spot_age = _parse_integer(
                    row["spot_age_ms"],
                    "spot_age_ms",
                    row_number,
                    errors,
                )

                if spot_age is not None and spot_age < 0:
                    errors.append(
                        f"Row {row_number}: negative spot_age_ms"
                    )

            decimals = {
                field: _parse_decimal(
                    row[field],
                    field,
                    row_number,
                    errors,
                )
                for field in DECIMAL_COLUMNS
            }

            spot_price = decimals["spot_price_usd"]
            mid_price = decimals["polymarket_mid_price"]
            spread = decimals["polymarket_spread"]
            imbalance = decimals["polymarket_imbalance"]

            if status == "aligned":
                if spot_price is None or spot_age is None:
                    errors.append(
                        f"Row {row_number}: aligned row missing spot data"
                    )

            if spot_price is not None and spot_price <= 0:
                errors.append(
                    f"Row {row_number}: spot price must be positive"
                )

            if mid_price is not None and not (
                Decimal("0") <= mid_price <= Decimal("1")
            ):
                errors.append(
                    f"Row {row_number}: midpoint outside [0, 1]"
                )

            if spread is not None and spread < 0:
                errors.append(
                    f"Row {row_number}: negative spread"
                )

            if imbalance is not None and not (
                Decimal("-1") <= imbalance <= Decimal("1")
            ):
                errors.append(
                    f"Row {row_number}: imbalance outside [-1, 1]"
                )

            if None in (session_id, timestamp_ms, sequence):
                continue

            identity = (
                session_id,
                token_id,
                sequence,
                timestamp_ms,
            )

            if identity in identities:
                duplicate_count += 1
                errors.append(
                    f"Row {row_number}: duplicate checkpoint identity"
                )
            else:
                identities.add(identity)

            token_key = (session_id, token_id)
            previous = previous_by_token.get(token_key)

            if previous is not None:
                previous_sequence, previous_timestamp = previous

                if (
                    sequence <= previous_sequence
                    or timestamp_ms <= previous_timestamp
                ):
                    temporal_violation_count += 1
                    errors.append(
                        f"Row {row_number}: temporal ordering violation"
                    )

            previous_by_token[token_key] = (
                sequence,
                timestamp_ms,
            )

    if row_count == 0:
        errors.append("CSV contains no research rows")

    return CSVValidationReport(
        path=str(path),
        row_count=row_count,
        token_count=len(tokens),
        duplicate_count=duplicate_count,
        temporal_violation_count=temporal_violation_count,
        errors=tuple(errors),
        valid=not errors,
    )
