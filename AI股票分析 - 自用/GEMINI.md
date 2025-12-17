# GEMINI.md - Agent Instruction Manual

## 🚀 Mission
You are an intelligent coding agent (Gemini, Claude, etc.) operating in this codebase.
This project is an **MCP (Model Context Protocol) Server**.
It exposes tools to fetch stock market data and financial reports.

## 🛠️ MCP Tool Usage

This server exposes the following tools via the MCP protocol.

### 1. `get_stock_info`
Search for a stock to get its standardized code.
- **Input**: `name_or_code` (str) - e.g., "Moutai" or "600519"
- **Returns**: JSON string `{"name": "...", "code": "..."}`.

### 2. `get_stock_daily_data`
Get OHLCV market data.
- **Input**:
    - `stock_code` (str): e.g., "600519.SH"
    - `start_date` (str): "YYYY-MM-DD"
    - `end_date` (str, optional): "YYYY-MM-DD"
- **Returns**: JSON string (List of records).

### 3. `get_financial_report`
Get fundamental data.
- **Input**:
    - `stock_code` (str)
    - `report_type` (str): "balance_sheet", "profit_sheet", "cash_flow_sheet", or "all".
    - `limit` (int): Number of periods (default 4).
- **Returns**: JSON string (Dict of lists).

### 4. `calculate_technical_indicators`
Compute metrics locally.
- **Input**:
    - `daily_data_json` (str): The raw output from `get_stock_daily_data`.
- **Returns**: JSON string with MA, RSI, Trend analysis.

## ⚙️ Configuration (Gemini CLI / Claude)

To use these tools, configure your MCP client to spawn this server.

**Command**:
```bash
python server.py
# Or if installed via fastmcp
fastmcp run server.py
```

**Claude Desktop Config (`claude_desktop_config.json`)**:
```json
{
  "mcpServers": {
    "StockTools": {
      "command": "python",
      "args": ["/absolute/path/to/server.py"]
    }
  }
}
```

**Gemini CLI Config**:

If you are using a Gemini CLI that supports MCP (like via a config file or command line):

1. **Config File (`mcp.json` or similar)**:
   ```json
   {
     "mcpServers": {
       "StockTools": {
         "command": "python",
         "args": ["c:/Users/leo/Desktop/Python/AI股票分析 - 自用/server.py"]
       }
     }
   }
   ```

2. **Command Line Flag**:
   ```bash
   gemini run --mcp-server="python c:/Users/leo/Desktop/Python/AI股票分析 - 自用/server.py"
   ```
   *(Note: Adjust the path to your actual project location)*

## 📂 Structure
- `server.py`: **MCP Server Entry Point**.
- `interface.py`: Underlying Logic Facade.
- `core/`: AKShare wrappers.
