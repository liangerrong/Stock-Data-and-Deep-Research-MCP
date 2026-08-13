# A-Share & HK Stock Financial Data MCP Server

基于 [Akshare](https://akshare.akfamily.xyz/) 与 [yfinance](https://github.com/ranaroussi/yfinance) 的股票财务数据 MCP 服务，供 Claude、Cursor 等 AI Agent 调用。支持 **A 股**和**港股**；可选连接免费的 Futu OpenD 获取港股主营构成。

---

## 与常规股票数据 MCP 的区别

专注于单个公司的深度调研，数据落地本地文件而非直接涌入模型上下文。效果详见 example。

## Anthropic initiating-coverage 专项适配

`build_historical_financial_package` 是为 Anthropic `claude-for-financial-services/equity-research` 中的 `initiating-coverage` plugin 工作流特化的 A 股及港股数据入口，重点服务其公司研究之后的历史财务建模、估值和图表任务。工具把 3–10 年历史三表、最新中报/季报、主营构成、股本与分红、公告索引、统一单位、币种角色和自动质量检查一次性落地为本地文件，减少 Agent 反复读取整份财报和在上下文中整理宽表所消耗的 token。

它是面向该工作流的数据准备适配层，不替代定期报告审计、会计政策判断、追溯重述核验或最终投资结论。

## 功能

- 无需 Token，开箱即用
- **A 股**：抓取利润表、资产负债表、现金流量表（来源：新浪财经）
- **港股**：核心三表及行情只使用 yfinance，不再抓取东方财富港股金额或财务指标
- **港股免费主营构成**：可选连接 Futu OpenD，抓取发行人披露的产品、地区、行业和业务收入
- 抓取最近 N 年的核心财务指标
- **A 股及港股历史研究包**：机械生成 3–10 年三表、核心实际值、补充指标、分红、来源清单及质量检查
- **港股币种隔离**：交易币种与财报币种分列；不确定的数据商换算金额自动隔离，禁止进入模型
- 支持公司名称反查股票代码 / Ticker
- 异常统一转为可读错误信息，MCP 进程不会因此崩溃
- 数据自动落地为本地 Markdown 文件

---

## 工具说明

### `search_stock`

输入公司名称，返回股票代码或港股 Ticker。

| 参数 | 必填 | 说明 |
|------|------|------|
| `stock_name` | ✅ | 公司名称或简称，如 `贵州茅台`、`腾讯控股`、`Tencent` |
| `market` | ❌ | `"cn"`（默认，A 股）或 `"hk"`（港股） |

> **注意：** 搜索港股时必须显式传入 `market="hk"`，否则将在 A 股数据库中查找，导致找不到结果。港股搜索底层使用 yfinance Search API，支持中英文名称，结果自动缓存。

### `get_financials`

输入股票代码，抓取当前市值及历史财务数据，保存为本地 `.md` 文件。

| 参数 | 必填 | 说明 |
|------|------|------|
| `stock_code` | ✅ | A 股六位代码（如 `600519`）或港股 Ticker（如 `0700.HK`） |
| `years` | ❌ | 抓取最近几年的数据，默认 3 |
| `output_dir` | ❌ | 输出目录的绝对路径，默认为当前目录 |

### `build_historical_financial_package`

为 A 股或港股财务建模和首次覆盖研究生成可审计的本地数据包。它保留三张原始报表，并额外生成标准化长表、核心历史实际值、补充指标、股本/分红资料、来源清单、单位字典、质量报告、清单和 ZIP 压缩包。

港股采用双币种模型：`quote_currency` 表示证券交易币种，`financial_currency` 表示发行人财报币种。例如腾讯为 `HKD/CNY`、汇丰为 `HKD/USD`、港交所为 `HKD/HKD`。核心三表使用 Yahoo Finance `info.financialCurrency` 明确标记。由于东方财富港股报告列表、主要指标和实际金额行为存在无法审计的币种冲突，MCP 默认完全停止抓取其港股金额与财务指标；兼容文件 `provider_statements_long.csv` 和 `financial_indicators_long.csv` 保留表头但不写入数值。

若本机安装并登录免费的 Futu OpenD，港股包会自动调用 `get_financials_revenue_breakdown`，将发行人披露的产品、地区、行业和业务收入写入 `business_composition.csv` 与 `business_composition_long.csv`。调用时不传 `currency_code`，保留接口返回的原始报告币种；质量检查会将该币种与 yfinance `financialCurrency` 对照。富途未配置、公司未披露某维度或接口没有历史数据时保持空值并输出 `WARN`。

数值型长表同时提供 `original_value`、`standardized_value`、`currency`、`original_unit`、`standard_unit`、`scale_to_standard` 和 `unit_basis`。例如主营比例从 0–1 换算为百分数、股本变动从万股换算为股；原值始终保留，不做不可追溯的覆盖。

| 参数 | 必填 | 说明 |
|------|------|------|
| `stock_code` | ✅ | A 股六位代码，如 `000408`；或港股代码，如 `0700.HK`、`00700` |
| `years` | ❌ | 年度历史期数，3–10 年，默认 5 |
| `output_dir` | ❌ | 输出目录的绝对路径，默认为当前目录 |
| `include_latest_interim` | ❌ | 是否附带最新一期中报/季报，默认 `true` |

自动检查包括三表完整性、年度覆盖、资产负债表平衡、核心字段覆盖、币种一致性、产品与地区分部覆盖、官方报告链接以及接口失败情况。`WARN` 不代表数据包不可用；它会指出需人工补齐的材料。行情价格、股数为 0 或金额币种为 `UNRESOLVED` 时，工具会明确禁止该值进入估值。

港股包额外生成：

- `market_identity.json`：规范代码、交易所、交易币种和财报币种
- `currency_manifest.csv`：逐数据集说明币种角色、来源及能否进入模型
- `business_composition.csv`：Futu OpenD 可用时返回的港股产品/地区/行业/业务收入
- `business_composition_long.csv`：上述主营构成的收入与占比长表
- `provider_statements_long.csv`：兼容保留的禁用数据集；港股不再写入东方财富金额
- `hk_report_metadata.csv`：兼容保留的禁用数据集；港股不再依赖东方财富币种标签

当前港股机械化边界：Futu 只提供收入和占比，不保证每家公司披露产品及地区，也不提供通用的分部成本/利润。缺失项目及报告级 HKEX 官方链接仍需从发行人年报或披露易补充，工具会输出 `WARN`，不会猜填。

---

## 安装

需要 Python 3.10+。

```bash
pip install "mcp>=1.0.0" akshare yfinance pandas tabulate
```

港股主营构成是可选的免费增强功能。先安装并登录 [Futu OpenD](https://openapi.futunn.com/futu-api-doc/opend/opend-cmd.html)，完成首次问卷和协议确认，再安装 SDK：

```bash
pip install futu-api
```

默认连接 `127.0.0.1:11111`。如 OpenD 使用其他地址，可设置 `FUTU_OPEND_HOST` 和 `FUTU_OPEND_PORT`。没有安装或登录 Futu 时，yfinance 三表仍正常生成，只是主营构成质量检查显示 `WARN`。该接入不要求付费数据订阅；不同地区的免费行情权限仍以富途当前规则为准。

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

`PYTHONPATH` 改为实际仓库的绝对路径。运行时所需网络访问：

| 数据源 | 用途 |
|--------|------|
| 新浪财经 | A 股财务三表 |
| 巨潮资讯 | A 股公司基本信息 / 股本 |
| 东方财富 | A 股历史行情（收盘价） |
| 东方财富 | A 股主营构成、分红历史 |
| Yahoo Finance | 港股行情、发行人币种财务三表及名称搜索 |
| Futu OpenAPI（可选免费登录） | 港股产品、地区、行业及业务收入构成；原始币种 |
| 东方财富 | 港股公司资料及带明确币种文字的分红；不再抓取港股财务金额或指标 |
| 香港交易所披露易 | 港股一级来源检索入口；当前不自动解析报告级链接 |

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

# 生成 A 股五年历史研究包
build_historical_financial_package("000408", years=5, output_dir="C:/research/000408")

# 生成港股五年历史研究包；交易币种和财报币种自动分开
build_historical_financial_package("0700.HK", years=5, output_dir="C:/research/0700")
```

---

## 测试

```bash
python -m pytest tests/
```

---

## 许可证

MIT。底层数据来自 [Akshare](https://github.com/akfamily/akshare) 与 [yfinance](https://github.com/ranaroussi/yfinance)，仅限个人与量化投研使用，禁止商业盈利用途。
