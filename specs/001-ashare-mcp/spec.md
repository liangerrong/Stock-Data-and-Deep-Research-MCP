# Feature Specification: A-Share Financial Data MCP Server

**Feature Branch**: `001-ashare-mcp`  
**Created**: 2026-02-26  
**Status**: Draft  
**Input**: User description: "这是一个供AI agent进行公司调研时使用的MCP，它的功能是预抓取某个公司最近几年的财务数据（加上当前股价和流通股数量），输出到当前文件夹下，供AI agent查阅可信接口的数据来调研和估值"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fetch Company Financial Data for Valuation (Priority: P1)

As an AI Agent conducting company research, I want to provide a company code to the MCP tool, so that it can automatically fetch the company's recent years of financial data, current stock price, and circulating shares, and save them as local files for me to read and base my valuation upon.

**Why this priority**: It is the core and only described use case for this feature - enabling AI agents to get reliable stock data for valuation research.

**Independent Test**: Can be fully tested by calling the MCP tool with a valid stock code (e.g., '600519') and verifying that the corresponding data files are created in the current directory containing correct historical financial data, current price, and circulating shares.

**Acceptance Scenarios**:

1. **Given** a valid A-share stock code (e.g., 600519), **When** the AI agent calls the data fetch tool, **Then** the tool fetches the recent years of financial data, current price, and circulating shares, and saves them to the current working directory, returning the file paths.
2. **Given** an invalid or non-existent stock code, **When** the AI agent calls the tool, **Then** the tool returns a clear error message indicating the stock cannot be found or data is unavailable.

---

### User Story 2 - Find Stock Code by Name (Priority: P2)

As an AI Agent conducting company research, I want to provide a company's name to a tool, so that it can return the exact stock code needed for fetching the financial data.

**Why this priority**: Often, users or agents only know the company name (e.g., "贵州茅台") rather than the exact stock code (e.g., "600519"). This is a critical helper function to make the primary feature usable.

**Independent Test**: Can be tested by providing a name like "贵州茅台" to the tool and checking if it returns the correct stock code "600519".

**Acceptance Scenarios**:

1. **Given** a valid stock name, **When** the agent queries the tool, **Then** the tool correctly returns the associated stock code.
2. **Given** a partial or slightly incorrect name, **When** the agent queries the tool, **Then** the tool attempts to find the closest match or returns a helpful "not found" message.

---

### Edge Cases

- What happens when a stock has limited financial history (e.g., newly listed companies)? The system should gracefully return whatever historical data is available without failing.
- How does the system handle network timeouts or upstream API limits when calling the reliable data source? It should catch the exceptions and return a clear error message to the AI agent rather than crashing.
- What happens if the current directory lacks write permissions? The tool should return a specific error explaining the file write failure.
- What if there are multiple companies matching a similar name? The tool should clarify or return the closest match.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose an MCP tool that accepts a stock code (and optionally years of history) as input parameters.
- **FR-002**: System MUST retrieve the current stock price and circulating shares for the specified stock.
- **FR-003**: System MUST retrieve the core financial data/indicators (e.g., revenue, net profit, balance sheet summaries) for the specified stock for the most recent years (e.g., last 3-5 years).
- **FR-004**: System MUST format the fetched data and write it to local file(s) in the current working directory.
- **FR-005**: System MUST return the absolute or relative paths of the generated files to the AI agent upon successful execution, so the agent can read them.
- **FR-006**: System MUST expose another MCP tool that accepts a stock name and returns the corresponding correct stock code.

### Assumptions

- **A-001**: Upstream reliable financial data source will be available and provide sufficient historical coverage natively.
- **A-002**: Output files will be in a format easily readable by LLMs (e.g., Markdown or CSV).

### Key Entities 

- **Market Snapshot**: Data entity representing real-time/latest market data, including current price and total circulating shares.
- **Financial History**: Data entity representing periodic financial reports, containing key indicators over the last N years.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Tool successfully fetches and saves all required data (price, shares, financial history) in under 15 seconds per request under normal network conditions.
- **SC-002**: Generates structured, readable output files whose contents accurately reflect the upstream data source without corruption or missing fields.
- **SC-003**: 100% of tool executions result in either successful file generation or a clear, actionable error message (0 silent crashes).
