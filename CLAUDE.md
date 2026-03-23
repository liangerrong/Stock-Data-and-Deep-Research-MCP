# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install "mcp>=1.0.0" akshare yfinance pandas tabulate

# Run all tests
python -m pytest tests/

# Run unit tests only
python -m pytest tests/unit/

# Run integration tests only
python -m pytest tests/integration/

# Run a single test file
python -m pytest tests/unit/test_akshare_client_financials.py

# Run a single test by name
python -m pytest tests/unit/test_akshare_client_financials.py::test_fetch_market_snapshot

# Start the MCP server manually (for debugging)
python -m src.server
```

## Architecture

This is an MCP (Model Context Protocol) server that wraps Akshare's A-share financial APIs for use by AI agents (Claude, Cursor, etc.).

**Entry point:** `src/server.py` — creates the MCP `Server` instance, registers two tools (`get_financials`, `search_stock`), and runs over stdio.

**Layer separation:**
- `src/tools/` — thin MCP tool handlers; catch all exceptions and return human-readable strings (never raise to the MCP layer)
- `src/core/akshare_client.py` — all Akshare API calls live here; raises `ValueError` for business-logic errors
- `src/utils/file_utils.py` — DataFrame → Markdown/CSV serialization helpers

**Data flow for `get_financials`:**
1. `fetch_market_snapshot()` — calls `stock_profile_cninfo` (巨潮资讯) for name/shares, then `stock_zh_a_hist` for the latest closing price
2. `fetch_raw_sina_reports()` — calls `stock_financial_report_sina` exactly three times to pre-fetch raw data for all report types, minimizing API calls
3. `fetch_latest_quarterly_report()` — reuses the raw data, filters to non-annual reports (NOT ending in `1231`), takes only the latest quarter row, merges on `报告日`
4. `fetch_financial_history()` — reuses the raw data, filters to annual reports (`报告日` ending in `1231`), merges on `报告日`
5. All DataFrames are written into a single `{stock_code}_financial_data.md` file in order: Market Snapshot → Latest Quarterly Report → Annual Financial History; only the file path is returned to the AI

**Stock code lookup (`search_stock`):** Full A-share name→code mapping is fetched once via `stock_info_a_code_name()` and cached locally at `src/core/.stock_codes_cache.json`. Subsequent calls read the cache. Supports exact and partial name matching.

**Output directory:** `get_financials` accepts an optional `output_dir`; falls back to `os.getcwd()` if the path is absent or invalid.

## Testing approach

Unit tests mock all Akshare calls (`@patch("src.core.akshare_client.ak.*")`). Integration tests mock at the tool-handler boundary (`@patch("src.tools.get_financials.fetch_*")`). No test hits the real network. Use `tempfile.TemporaryDirectory` for file output in tests.

## MCP client configuration

```json
{
  "mcpServers": {
    "ashare-mcp": {
      "command": "python",
      "args": ["-m", "src.server"],
      "env": {
        "PYTHONPATH": "C:/absolute/path/to/this/repo"
      }
    }
  }
}
```

The server requires network access to 东方财富, 新浪财经, and 巨潮资讯 endpoints at runtime.
