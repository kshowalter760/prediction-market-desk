
import csv

import pytest

from prediction_desk.research_csv_validation import (
    EXPECTED_COLUMNS,
    validate_research_csv,
)


@pytest.fixture
def valid_row():
    return {
        "token_id": "token_1",
        "session_id": "3",
        "timestamp_ms": "1000",
        "message_sequence": "10",
        "alignment_status": "aligned",
        "spot_price_usd": "77568.9",
        "spot_age_ms": "167",
        "spot_return_pct": "",
        "polymarket_mid_price": "0.0145",
        "polymarket_mid_change": "",
        "polymarket_spread": "0.009",
        "polymarket_imbalance": "-0.7638264135290221432251187001",
    }


def write_csv(tmp_path, rows, columns=EXPECTED_COLUMNS):
    path = tmp_path / "research.csv"

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    return path


def test_valid_csv(tmp_path, valid_row):
    path = write_csv(tmp_path, [valid_row])
    report = validate_research_csv(path)

    assert report.valid
    assert report.row_count == 1
    assert report.token_count == 1
    assert report.errors == ()


def test_duplicate_identity(tmp_path, valid_row):
    path = write_csv(tmp_path, [valid_row, valid_row])
    report = validate_research_csv(path)

    assert not report.valid
    assert report.duplicate_count == 1


def test_temporal_sequence_violation(tmp_path, valid_row):
    second = valid_row | {
        "timestamp_ms": "2000",
        "message_sequence": "9",
    }

    path = write_csv(tmp_path, [valid_row, second])
    report = validate_research_csv(path)

    assert not report.valid
    assert report.temporal_violation_count == 1


def test_temporal_timestamp_violation(tmp_path, valid_row):
    second = valid_row | {
        "timestamp_ms": "900",
        "message_sequence": "11",
    }

    path = write_csv(tmp_path, [valid_row, second])
    report = validate_research_csv(path)

    assert not report.valid
    assert report.temporal_violation_count == 1


def test_invalid_schema(tmp_path, valid_row):
    columns = EXPECTED_COLUMNS[:-1]
    row = {
        key: value
        for key, value in valid_row.items()
        if key in columns
    }

    path = write_csv(tmp_path, [row], columns)
    report = validate_research_csv(path)

    assert not report.valid
    assert "schema" in report.errors[0]


def test_invalid_decimal(tmp_path, valid_row):
    row = valid_row | {
        "spot_price_usd": "not-a-number",
    }

    path = write_csv(tmp_path, [row])
    report = validate_research_csv(path)

    assert not report.valid


def test_nonfinite_decimal(tmp_path, valid_row):
    row = valid_row | {
        "polymarket_mid_price": "NaN",
    }

    path = write_csv(tmp_path, [row])
    report = validate_research_csv(path)

    assert not report.valid


def test_negative_spread(tmp_path, valid_row):
    row = valid_row | {
        "polymarket_spread": "-0.01",
    }

    path = write_csv(tmp_path, [row])
    report = validate_research_csv(path)

    assert not report.valid


def test_missing_spot_status(tmp_path, valid_row):
    row = valid_row | {
        "alignment_status": "missing_spot",
        "spot_price_usd": "",
        "spot_age_ms": "",
    }

    path = write_csv(tmp_path, [row])
    report = validate_research_csv(path)

    assert report.valid


def test_aligned_row_requires_spot_data(tmp_path, valid_row):
    row = valid_row | {
        "spot_price_usd": "",
    }

    path = write_csv(tmp_path, [row])
    report = validate_research_csv(path)

    assert not report.valid


def test_invalid_alignment_status(tmp_path, valid_row):
    row = valid_row | {
        "alignment_status": "unknown",
    }

    path = write_csv(tmp_path, [row])
    report = validate_research_csv(path)

    assert not report.valid


def test_empty_csv(tmp_path):
    path = write_csv(tmp_path, [])
    report = validate_research_csv(path)

    assert not report.valid
    assert report.row_count == 0


def test_distinct_tokens_same_timestamp(tmp_path, valid_row):
    second = valid_row | {
        "token_id": "token_2",
    }

    path = write_csv(tmp_path, [valid_row, second])
    report = validate_research_csv(path)

    assert report.valid
    assert report.token_count == 2


def test_invalid_integer(tmp_path, valid_row):
    row = valid_row | {
        "message_sequence": "10.5",
    }

    path = write_csv(tmp_path, [row])
    report = validate_research_csv(path)

    assert not report.valid
