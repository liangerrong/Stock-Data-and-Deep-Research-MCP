# Interface Contracts: MCP Tools

This server exposes exactly two external tool interfaces.

## Tool 1: `search_stock`
**Description**: Find the exact 6-digit A-share stock code corresponding to a given company name.
**Input Schema** (JSON Schema):
```json
{
  "type": "object",
  "properties": {
    "stock_name": {
      "type": "string",
      "description": "The name of the company (e.g., '贵州茅台')"
    }
  },
  "required": ["stock_name"]
}
```
**Output**: A clear string showing the matched stock code (`600519`) or an error message if not found.

## Tool 2: `get_financials`
**Description**: Fetch the current market snapshot (price, circulating shares) and recent years of financial data, save them to the current directory, and return the local file paths.
**Input Schema** (JSON Schema):
```json
{
  "type": "object",
  "properties": {
    "stock_code": {
      "type": "string",
      "description": "The exact 6-digit stock code (e.g., '600519')"
    },
    "years": {
      "type": "integer",
      "description": "Number of recent years of financial data to fetch (default: 5)"
    }
  },
  "required": ["stock_code"]
}
```
**Output**: A string indicating success and containing absolute paths to the newly generated data files. Example:
`Data saved successfully. Financials: C:\path\to\600519_financials.md, Market Data: C:\path\to\600519_market.md`
