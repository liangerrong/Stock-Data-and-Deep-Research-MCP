# A-Share Financial Data MCP Server

基于 [Akshare](https://akshare.akfamily.xyz/) 的 A 股财务数据 MCP 服务，供 Claude、Cursor 等 AI Agent 调用。

---
## 与常规股票数据MCP的区别
专注于于单个公司的深度调研。效果详见example。

## 功能

- 无需 Token，开箱即用
- 抓取最近 N 年的核心财务指标（利润表、资产负债表）
- 异常统一转为可读错误信息，MCP 进程不会因此崩溃
- 支持公司名称反查股票代码
- 数据自动落地为本地 Markdown 文件，避免大量数据直接涌入模型上下文

---

## 工具说明

### `search_stock`

输入公司名称，返回六位 A 股代码。

- `stock_name`（必填）：公司名称或简称，如 `贵州茅台`

### `get_financials`

输入股票代码，抓取当前市值及历史财务数据，保存为本地 `.md` 文件。

- `stock_code`（必填）：六位 A 股代码，如 `600519`
- `years`（选填，默认 5）：抓取最近几年的数据

---

## 安装

需要 Python 3.10+。

```bash
pip install "mcp>=1.0.0" akshare pandas
```

---

## 配置

以 Claude Desktop 或 Cursor 为例：

```json
{
  "mcpServers": {
    "ashare-mcp": {
      "command": "python",
      "args": ["-m", "src.server"],
      "env": {
        "PYTHONPATH": "C:/path/to/ashare-mcp"
      }
    }
  }
}
```

运行时需要能访问东方财富、新浪财经等数据接口。`PYTHONPATH` 改为实际仓库路径。

---

## 测试

```bash
python -m pytest tests/
```

---

## 许可证

MIT。底层数据来自 [Akshare](https://github.com/akfamily/akshare)，仅限个人与量化投研使用，禁止商业盈利用途。
