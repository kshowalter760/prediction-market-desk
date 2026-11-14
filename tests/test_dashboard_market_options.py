
import pandas as pd
import pytest

from prediction_desk.dashboard_data import prepare_market_options


def make_tokens(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "token_id",
            "market_id",
            "asset",
            "question",
            "outcome_name",
        ],
    )


def test_registered_market_label():
    tokens = make_tokens([
        (
            "123456789012345678901234567890",
            "market-1",
            "BTC",
            "Will Bitcoin rise?",
            "Yes",
        ),
    ])

    result = prepare_market_options(tokens)

    assert len(result) == 1
    assert result.iloc[0]["registry_status"] == "Registered"
    assert "BTC" in result.iloc[0]["display_name"]
    assert "Will Bitcoin rise?" in result.iloc[0]["display_name"]
    assert "Yes" in result.iloc[0]["display_name"]
    assert "12345678...567890" in result.iloc[0]["display_name"]


def test_unregistered_market_label():
    tokens = make_tokens([
        (
            "123456789012345678901234567890",
            None,
            None,
            None,
            None,
        ),
    ])

    result = prepare_market_options(tokens)

    assert result.iloc[0]["registry_status"] == "Unregistered"
    assert "Unknown asset" in result.iloc[0]["display_name"]
    assert "Unregistered market" in result.iloc[0]["display_name"]


def test_duplicate_token_prefers_complete_metadata():
    token_id = "123456789012345678901234567890"

    tokens = make_tokens([
        (token_id, None, None, None, None),
        (
            token_id,
            "market-1",
            "ETH",
            "Will Ethereum rise?",
            "Up",
        ),
    ])

    result = prepare_market_options(tokens)

    assert len(result) == 1
    assert result.iloc[0]["registry_status"] == "Registered"
    assert "ETH" in result.iloc[0]["display_name"]


def test_multiple_unique_tokens():
    tokens = make_tokens([
        ("token-a", "market-1", "BTC", "Question A", "Yes"),
        ("token-b", "market-2", "ETH", "Question B", "No"),
    ])

    result = prepare_market_options(tokens)

    assert len(result) == 2
    assert result["token_id"].nunique() == 2


def test_invalid_token_identifiers():
    tokens = make_tokens([
        (None, None, None, None, None),
        ("", None, None, None, None),
        ("   ", None, None, None, None),
        ("valid-token", None, None, None, None),
    ])

    result = prepare_market_options(tokens)

    assert len(result) == 1
    assert result.iloc[0]["token_id"] == "valid-token"


def test_empty_input():
    tokens = make_tokens([])

    result = prepare_market_options(tokens)

    assert result.empty
    assert "display_name" in result.columns
    assert "registry_status" in result.columns


def test_missing_required_column():
    tokens = make_tokens([
        ("token-a", None, "BTC", "Question", "Yes"),
    ])

    tokens = tokens.drop(columns=["question"])

    with pytest.raises(ValueError, match="Missing required columns"):
        prepare_market_options(tokens)


def test_original_dataframe_not_modified():
    tokens = make_tokens([
        ("token-a", "market-1", "BTC", "Question", "Yes"),
    ])

    original = tokens.copy(deep=True)

    prepare_market_options(tokens)

    pd.testing.assert_frame_equal(tokens, original)
