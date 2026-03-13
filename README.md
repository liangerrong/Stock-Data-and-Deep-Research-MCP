# A-Share & HK Stock Financial Data MCP Server

基于 [Akshare](https://akshare.akfamily.xyz/) 与 [yfinance](https://github.com/ranaroussi/yfinance) 的股票财务数据 MCP 服务，供 Claude、Cursor 等 AI Agent 调用。支持 **A 股**和**港股**。

---

## 与常规股票数据 MCP 的区别

专注于单个公司的深度调研，数据落地本地文件而非直接涌入模型上下文。

---
## 与常规股票数据MCP的区别
专注于于单个公司的深度调研。效果详见example。

## 功能

- 无需 Token，开箱即用
- **A 股**：抓取利润表、资产负债表、现金流量表（来源：新浪财经）
- **港股**：抓取年度财务三表（来源：yfinance）
- 抓取最近 N 年的核心财务指标
- 支持公司名称反查股票代码 / Ticker
- 异常统一转为可读错误信息，MCP 进程不会因此崩溃
- 数据自动落地为本地 Markdown 文件

---

## 工具说明

### `search_stock`

输入公司名称，返回股票代码或港股 Ticker。

| 参数 | 必填 | 说明 |
|------|------|------|
| `stock_name` | ✅ | 公司名称或简称，如 `贵州茅台`、`腾讯控股` |
| `market` | ❌ | `"cn"`（默认，A 股）或 `"hk"`（港股） |

### `get_financials`

输入股票代码，抓取当前市值及历史财务数据，保存为本地 `.md` 文件。

| 参数 | 必填 | 说明 |
|------|------|------|
| `stock_code` | ✅ | A 股六位代码（如 `600519`）或港股 Ticker（如 `0700.HK`） |
| `years` | ❌ | 抓取最近几年的数据，默认 3 |
| `output_dir` | ❌ | 输出目录的绝对路径，默认为当前目录 |

---

## 安装

需要 Python 3.10+。

```bash
pip install "mcp>=1.0.0" akshare yfinance pandas tabulate
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
        "PYTHONPATH": "C:/path/to/this/repo"
      }
    }
  }
}
```

`PYTHONPATH` 改为实际仓库的绝对路径。运行时需要能访问东方财富、新浪财经（A 股）及 Yahoo Finance（港股）数据接口。

---

## 使用示例

```
# 查找 A 股代码
search_stock("贵州茅台")
→ Found stock code for 贵州茅台: 600519

# 查找港股 Ticker
search_stock("腾讯控股", market="hk")
→ Found HK stock ticker for 腾讯控股: 0700.HK

# 获取 A 股财务数据
get_financials("600519", years=3)

# 获取港股财务数据
get_financials("0700.HK", years=3)
```

---

## 测试

```bash
python -m pytest tests/
```

---

## 许可证

MIT。底层数据来自 [Akshare](https://github.com/akfamily/akshare) 与 [yfinance](https://github.com/ranaroussi/yfinance)，仅限个人与量化投研使用，禁止商业盈利用途。
