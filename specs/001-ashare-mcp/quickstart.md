# Quickstart & Test Scenarios

## Test Scenarios

### Scenario 1: Search Stock Code by Name
1. Run the MCP server.
2. Call the `search_stock` tool with the argument: `{"stock_name": "贵州茅台"}`.
3. **Expected Result**: Output indicates `600519`.

### Scenario 2: Fetch Financial Data
1. Run the MCP server.
2. Call the `get_financials` tool with the arguments: `{"stock_code": "600519", "years": 5}`.
3. **Expected Result**: The tool fetches data and saves files (e.g., `600519_market.md`, `600519_financials.md`) in the current directory and returns the absolute paths to these files.

### Scenario 3: Error Handling (Invalid Code/Name)
1. Run the MCP server.
2. Call the `get_financials` tool with the arguments: `{"stock_code": "999999"}`.
3. **Expected Result**: The tool returns an error message indicating that no data was found or the code is invalid.
4. Call the `search_stock` tool with the argument: `{"stock_name": "不存在的公司"}`.
5. **Expected Result**: Returns an error message.
