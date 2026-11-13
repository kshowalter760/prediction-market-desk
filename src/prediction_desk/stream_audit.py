
from dataclasses import dataclass

from prediction_desk.continuity import (
    ContinuityReport,
    assess_trade_continuity,
)
from prediction_desk.spot import SpotTrade


@dataclass(frozen=True)
class StreamContinuitySummary:
    btc: ContinuityReport
    eth: ContinuityReport
    total_potential_gaps: int
    total_missing_ids: int


def assess_stream_continuity(trades):
    trades = list(trades)

    if not all(
        isinstance(trade, SpotTrade)
        for trade in trades
    ):
        raise TypeError("Expected SpotTrade objects")

    btc_trades = [
        trade
        for trade in trades
        if trade.asset == "BTC"
    ]

    eth_trades = [
        trade
        for trade in trades
        if trade.asset == "ETH"
    ]

    if len(btc_trades) + len(eth_trades) != len(trades):
        raise ValueError("Unsupported trade asset")

    btc_report = assess_trade_continuity(
        btc_trades,
        "BTC",
    )

    eth_report = assess_trade_continuity(
        eth_trades,
        "ETH",
    )

    all_gaps = (
        btc_report.gaps + eth_report.gaps
    )

    return StreamContinuitySummary(
        btc=btc_report,
        eth=eth_report,
        total_potential_gaps=len(all_gaps),
        total_missing_ids=sum(
            gap.missing_id_count
            for gap in all_gaps
        ),
    )
