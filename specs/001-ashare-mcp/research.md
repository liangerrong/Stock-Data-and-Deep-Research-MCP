# Research: A-Share Financial Data MCP Server

## Technical Unknowns and Decisions

1. **Data Source SDK**
   - **Decision**: Use `akshare`.
   - **Rationale**: It is free, requires no tokens or points, and provides comprehensive financial reports (balance sheets, income statements, cash flows), current prices, and circulating shares in a few lines of code via the `pandas` DataFrame format.
   - **Alternatives considered**: Tushare (rejected due to high point requirements for financial data) and Baostock (rejected due to unergonomic API requiring manual loop over years/quarters).

2. **MCP Implementation Framework**
   - **Decision**: Use the official `mcp` standard library for Python.
   - **Rationale**: Standard library allows easy standard-compliant creation of Model Context Protocol tools.
   - **Alternatives considered**: None, this is the standard.

3. **Outputs**
   - **Decision**: Save data as Markdown tables and CSVs to the current working directory, then return the absolute paths in the tool's text response.
   - **Rationale**: The AI agent executing this can easily read Markdown or CSV using local tools, avoiding huge string outputs in the MCP response itself, and fulfilling the requirement to output into the local folder.

4. **Name-to-Code Implementation**
   - **Decision**: Use `akshare`'s `stock_zh_a_spot_em` or similar table to search via name locally, or use `akshare.stock_info_a_code_name()` to map name to code.
   - **Rationale**: Allows offline or low-latency matching from name to stock code.
