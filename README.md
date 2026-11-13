# Prediction Markets Desk

A Python-based research and market-data engineering platform for collecting, reconstructing, and analyzing cryptocurrency prediction markets.

The project focuses on Polymarket BTC and ETH markets, with supporting Coinbase spot-market data, persistent SQLite storage, historical replay, and research-quality validation.

**Current version:** 0.1.0  
**Status:** Research prototype

## Overview

Prediction Markets Desk is designed to investigate how prediction-market prices, order-book liquidity, and cryptocurrency spot-market movements relate over time.

Rather than relying exclusively on periodically sampled prices, the system incorporates market-data collection, historical reconstruction, cross-market alignment, and data-quality checks.

The goal is to provide a reproducible foundation for quantitative research and future real-time monitoring tools.

## Core Capabilities

### Market Discovery and Registry

- Discover cryptocurrency prediction markets.
- Identify directional and price-target market contracts.
- Store market metadata and outcome token identifiers.
- Maintain a persistent market registry.

### Market Data Collection

- Collect Polymarket order-book data.
- Support live market-data collection workflows.
- Collect Coinbase spot-market observations.
- Persist historical observations in SQLite.

### Order-Book Reconstruction

- Process order-book snapshots and incremental updates.
- Reconstruct historical order-book states.
- Audit reconstruction integrity.
- Compare reconstructed states against available snapshot evidence.

### Liquidity and Market Analysis

- Analyze bid-ask spreads and available liquidity.
- Examine market quote changes.
- Study liquidity conditions across outcome tokens.
- Generate research and diagnostic reports.

### Cross-Market Research

- Align prediction-market observations with cryptocurrency spot-market data.
- Examine market behavior over configurable historical intervals.
- Apply observation-age and alignment-quality constraints.
- Export checkpoint-level research datasets.

### Research Integrity

- Validate exported CSV structure and temporal consistency.
- Check historical export reproducibility.
- Evaluate snapshot-pair verification evidence.
- Track checkpoint coverage and research-readiness limitations.

## Architecture

The project uses a Python `src/` package layout.

```text
prediction-markets-desk/
├── src/
│   └── prediction_desk/
│       ├── discovery.py
│       ├── polymarket.py
│       ├── storage.py
│       ├── coordinator.py
│       └── ... additional research modules
├── tests/
├── run_market_registry.py
├── run_coordinated_session.py
├── run_checkpoint_research.py
├── run_snapshot_pair_report.py
├── run_quality_report.py
├── run_cross_market_report.py
├── pyproject.toml
└── .gitignore
```

The system is organized around market discovery, data collection, persistence, reconstruction, analytics, and research reporting.

## Requirements

- Python 3.11 or newer, as declared in project metadata
- Internet connectivity for live market-data collection
- SQLite, available through the Python standard library

**Verified development environment:** Python 3.14.4 on Windows 11. Compatibility with Python 3.11 has not yet been independently tested.

## Installation

Clone the repository after publication:

```bash
git clone <https://github.com/kshowalter760/prediction-market-desk.git>
cd prediction-markets-desk
```

Create and activate a virtual environment.

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project with development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Verify the installation:

```powershell
python -m pip check
python -m pytest -q
```

## Usage

Run commands from the project root.

### Market Registry

```powershell
python run_market_registry.py
```

The registry runner uses the default SQLite database path:

`data/prediction_markets.db`

### Coordinated Data Collection

```powershell
python run_coordinated_session.py --token-id YOUR_TOKEN_ID --duration 30
```

The `--token-id` option is required and may be repeated for multiple outcome tokens.

The runner also accepts `--database` to select the SQLite database path.

### Historical Checkpoint Research

```powershell
python run_checkpoint_research.py --session-id 3 --asset BTC --interval 5 --max-spot-age-ms 5000
```

The runner supports BTC and ETH research configurations and produces checkpoint-level research exports.

A valid session ID must already exist in the local database.

### Snapshot-Pair Report

```powershell
python run_snapshot_pair_report.py --session-id 3
```

Examines available snapshot-pair evidence for a recorded session.

### Data Quality Report

```powershell
python run_quality_report.py
```

Runs the project's data-quality reporting workflow.

### Cross-Market Report

```powershell
python run_cross_market_report.py --max-age-ms 5000 --limit 10
```

Supports configurable observation-age filtering and result limits.

## Testing

The project includes automated tests covering market-data models, storage, ingestion, reconstruction, analytics, and research validation.

At the latest verified checkpoint:

**462 tests passed.**

The project has also passed editable-installation verification, dependency consistency checks, and testing in a separate Python 3.14.4 virtual environment.

Run the full suite with:

```powershell
python -m pytest -q
```

## Research Validation and Limitations

Historical research output should not automatically be interpreted as independently verified market history.

In particular:

- Matching snapshot endpoints do not establish that every intermediate reconstructed checkpoint is correct.
- Missing snapshot coverage limits independent replay verification.
- Aligned observations are not necessarily independently validated observations.
- Statistical associations do not establish causality or predictive trading performance.
- Research datasets may contain incomplete or unverified intervals.

Two historical BTC research exports were validated for CSV integrity and reproduced byte-for-byte from the same local database state.

However, the examined sessions did not meet the project's independent replay verification and research-readiness criteria.

**The current project is a research prototype, not a validated trading strategy or production trading system.**

## Data and Repository Policy

Local databases, generated reports, cached data, virtual environments, and credentials are excluded from version control.

The public repository is intended to contain application source code, tests, configuration, and documentation—not private credentials or locally collected market datasets.

## Roadmap

Planned development includes:

- A web-based research dashboard
- Live market monitoring and visualizations
- Historical session exploration
- Research-quality indicators and diagnostic views
- Configurable alerts
- Paper-trading and strategy evaluation workflows

These are future development goals and should not be interpreted as implemented production features.

## Project Purpose

Prediction Markets Desk is an ongoing quantitative software engineering project exploring the intersection of prediction markets, cryptocurrency market data, data infrastructure, and reproducible research.

Its emphasis is on building reliable data pipelines, validating historical observations, and creating a foundation for more advanced market intelligence tools.