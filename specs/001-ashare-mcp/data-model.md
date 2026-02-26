# Data Model: A-Share Financial Data MCP Server

## Entities

### `MarketSnapshot`
Represents the current market status of the stock.
- `stock_code` (str): 6-digit stock code
- `stock_name` (str): Name of the company
- `current_price` (float): Current trading price
- `circulating_shares` (float): Number of circulating shares

### `FinancialHistory`
Represents a collection of periodic financial indicators or report lines over the last N years.
- `stock_code` (str): 6-digit stock code
- `reports` (List):
  - `report_date` (str): Date of the report
  - `metrics` (Dict): Key-value pairs of financial indicators/items

*Note: Since the output is written to CSV/Markdown and not stored in a local database, these entities act as data transfer objects (DTOs) representing the DataFrame rows extracted from `akshare` before serialization.*
