# Prediction Markets Desk

A Python-based research and market-data engineering platform for collecting, reconstructing, and analyzing cryptocurrency prediction markets.

The project focuses on Polymarket BTC and ETH markets, with supporting Coinbase spot-market data, persistent SQLite storage, historical replay, research-quality validation, and a browser-based research dashboard.

**Current version:** 0.1.0  
**Status:** Research prototype with local web dashboard

## Overview

Prediction Markets Desk is designed to investigate how prediction-market prices, order-book liquidity, and cryptocurrency spot-market movements relate over time.

Rather than relying exclusively on periodically sampled prices, the system incorporates market-data collection, historical reconstruction, cross-market alignment, and data-quality checks.

The project also includes a Streamlit dashboard for exploring registered markets, historical order-book observations, and data-collection sessions.

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

### Web Dashboard

- Explore registered BTC and ETH prediction markets.
- Filter markets by asset.
- Inspect historical order-book snapshots.
- Review Polymarket and Coinbase collection-session records.
- Display summary metrics for stored market data.
- Access existing SQLite research data through a read-only database layer.

The dashboard is currently intended for local research and historical data inspection. It does not yet provide verified real-time market monitoring or automated trading.

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
│       ├── dashboard_data.py
│       └── ... additional research modules
├── tests/
│   ├── test_dashboard_data.py
│   └── ... additional automated tests
├── dashboard.py
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

The dashboard follows a separation-of-responsibilities approach:

- `dashboard.py` handles the Streamlit interface, navigation, tables, and summary metrics.
- `src/prediction_desk/dashboard_data.py` handles read-only SQLite queries and row counts.
- The existing SQLite database remains the source of stored research observations.

This architecture allows dashboard data access to be tested independently of the browser interface.

## Requirements

- Python 3.11 or newer, as declared in project metadata
- Internet connectivity for live market-data collection
- SQLite, available through the Python standard library
- Streamlit and pandas for the optional web dashboard

**Verified development environment:** Python 3.14.4 on Windows 11. Compatibility with Python 3.11 has not yet been independently tested.

## Installation

Clone the repository:

```powershell
git clone https://github.com/kshowalter760/prediction-market-desk.git
cd prediction-market-desk
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

To install the dashboard dependencies as well:

```powershell
python -m pip install -e ".[dev,dashboard]"
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

## Web Dashboard

Prediction Markets Desk includes a local, browser-based research dashboard built with Streamlit.

The dashboard currently provides:

- **Market Explorer:** Browse registered BTC and ETH prediction markets and filter by asset.
- **Order Book History:** Inspect stored historical bid, ask, spread, and observation timestamps.
- **Collection Health:** Review Polymarket and Coinbase stream-session records.
- **Research Summary:** View counts of registered markets, outcomes, order-book snapshots, and spot trades.

The dashboard uses the existing SQLite research database through a read-only data-access module.

### Dashboard Installation

Install the package with dashboard and development dependencies:

```powershell
python -m pip install -e ".[dev,dashboard]"
```

### Launch the Dashboard

From the project root:

```powershell
python -m streamlit run dashboard.py
```

Open the following address in your browser:

`http://localhost:8501`

Streamlit may open the browser automatically.

To stop the server, press `Ctrl+C` in the terminal.

### Database Requirements

The dashboard expects an existing SQLite research database at:

`data/prediction_markets.db`

Database files are excluded from Git version control.

A fresh installation must initialize and populate its own research database using the project's existing registry and collection workflows.

The dashboard does not create, migrate, or populate the database automatically.

### Dashboard Data Integrity

The dashboard's data-access layer:

- Opens SQLite databases in read-only mode.
- Rejects missing database files.
- Supports parameterized SQL queries.
- Restricts row-count queries to supported tables.
- Prevents database writes through its read-only connection.

These behaviors are covered by dedicated automated tests.

**Research limitation:** The dashboard displays stored historical observations. It does not currently provide verified live market prices, automated trading, or independently validated trading signals.

## Testing

The project includes automated tests covering market-data models, storage, ingestion, reconstruction, analytics, research validation, and dashboard data access.

At the latest verified checkpoint:

**468 tests passed.**

This includes six dashboard-specific tests covering:

- Query results
- Parameterized queries
- Row counts
- Unsupported table names
- Missing database handling
- Read-only database enforcement

The project has also passed editable-installation verification and dependency consistency checks.

An earlier version of the research backend was successfully tested in a separate Python 3.14.4 virtual environment.

Run the full suite with:

```powershell
python -m pytest -q
```

Check installed dependency consistency with:

```powershell
python -m pip check
```

## Research Validation and Limitations

Historical research output should not automatically be interpreted as independently verified market history.

In particular:

- Matching snapshot endpoints do not establish that every intermediate reconstructed checkpoint is correct.
- Missing snapshot coverage limits independent replay verification.
- Aligned observations are not necessarily independently validated observations.
- Statistical associations do not establish causality or predictive trading performance.
- Research datasets may contain incomplete or unverified intervals.
- Stored stream-session status does not independently establish that a live connection remains active.
- Historical bid and ask observations may be incomplete or unavailable.

Two historical BTC research exports were validated for CSV integrity and reproduced byte-for-byte from the same local database state.

However, the examined sessions did not meet the project's independent replay verification and research-readiness criteria.

**The current project is a research prototype, not a validated trading strategy or production trading system.**

## Data and Repository Policy

Local databases, generated reports, cached data, virtual environments, and credentials are excluded from version control.

The public repository is intended to contain application source code, tests, configuration, and documentation—not private credentials or locally collected market datasets.

The Streamlit dashboard currently operates against a local research database and does not require exposing that database through a publicly accessible server.

## Roadmap

### Completed Foundations

- Market discovery and registry
- Polymarket and Coinbase data-collection infrastructure
- Persistent SQLite research storage
- Historical order-book reconstruction
- Liquidity and cross-market analytics
- Historical replay and research-quality validation
- Local Streamlit dashboard foundation
- Automated dashboard database-access tests

### Planned Development

- Enhanced market monitoring and filtering
- Historical price and liquidity visualizations
- Market-specific research views
- Observation-quality indicators and diagnostic panels
- Live dashboard integration with existing data collectors
- Historical session exploration
- Configurable alerts
- Paper-trading and strategy evaluation workflows
- Expansion into additional prediction-market categories

Planned features should not be interpreted as implemented production capabilities.

## Project Purpose

Prediction Markets Desk is an ongoing quantitative software engineering project exploring the intersection of prediction markets, cryptocurrency market data, data infrastructure, and reproducible research.

Its emphasis is on building reliable data pipelines, validating historical observations, and developing practical market intelligence tools.

The long-term objective is to evolve the research platform into an interactive, extensible prediction-markets intelligence desk while maintaining clear distinctions between observed data, derived analytics, and unverified trading hypotheses.