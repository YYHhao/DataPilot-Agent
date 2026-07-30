# DataPilot Agent

DataPilot Agent 是一个面向企业数据源的多 Agent 数据分析示例项目。用户提交自然语言问题和已登记的 `dataset_id`，系统会检查数据源结构、生成只读 SQL、执行分析、复核证据，并生成可追溯的 Markdown 报告。

Planner 和 Text-to-SQL Agent 均由大模型驱动。项目使用 OpenAI-compatible 接口，可连接 OpenAI 或其他兼容服务，并可将数据源配置为 SQLite 或 PostgreSQL。

## 核心能力

- 使用 LangGraph 编排分析工作流；
- 使用结构化模型输出生成分析计划和 SQL；
- SQL 失败后由 Agent 根据错误反馈自动修复；
- 使用 BM25 与 Embedding 混合检索业务指标和字段语义；
- 通过语义层统一收入、订单量和客单价等业务口径；
- 提供 MCP Server，将 Schema、语义检索和只读查询暴露为标准工具；
- 记录节点耗时、模型 Token、检索结果、SQL 和错误类型；
- 支持 SQLite 和 PostgreSQL；
- 通过数据集目录和表白名单限制可访问范围；
- 只允许执行 `SELECT` 或 `WITH` 查询；
- 拒绝写操作、危险函数、多语句和 SQL 注释；
- 限制查询超时和最大返回行数；
- 对高风险请求设置人工审批节点；
- 保存运行状态、执行轨迹和 Markdown 报告；
- 提供 FastAPI、CLI、Docker、测试和离线评估入口。

## 工作流程

```mermaid
flowchart LR
    U[问题和 dataset_id] --> P[Planner]
    P --> G{需要审批?}
    G -->|是且未批准| S[保存等待审批状态]
    G -->|否或已批准| C[Schema Agent]
    C --> K[BM25 + Embedding 语义检索]
    K --> Q[SQL Agent]
    Q --> V[SQL 安全校验与只读执行]
    V --> E{执行成功?}
    E -->|否且未超过重试次数| F[SQL Repair Agent]
    F --> V
    E -->|是或重试结束| A[Analyst]
    A --> R[Reviewer]
    R --> O[生成并保存报告]
```

各组件职责：

| 组件 | 职责 |
| --- | --- |
| Planner | 判断分析类型、生成步骤并识别高风险意图 |
| Schema Agent | 读取目录允许的数据表结构 |
| Semantic Retriever | 混合检索指标定义、维度说明和业务规则 |
| SQL Agent | 根据问题和 Schema 生成 1～5 条分析 SQL |
| SQL Repair Agent | 根据数据库错误和安全拒绝原因修复 SQL |
| SQL Runtime | 独立校验并以只读方式执行 SQL |
| Analyst | 从成功执行的查询中整理证据和发现 |
| Reviewer | 检查执行结果、表权限和证据链完整性 |
| Reporter | 生成包含 SQL、结果摘要和复核结论的报告 |

## 环境要求

- Miniconda 或 Anaconda；
- Windows PowerShell、Linux 或 macOS；
- Python 3.11～3.14；
- Docker 可选；
- PostgreSQL 可选。

以下命令均需在项目根目录 `DataPilot-Agent` 中执行。

## 快速开始

### 1. 创建 Conda 环境

Windows、Linux 和 macOS 使用相同命令：

```bash
conda create -n datapilot python=3.11 -y
conda activate datapilot
```

如果出现 `conda activate` 不可用，请先执行 `conda init`，关闭并重新打开终端。

### 2. 安装依赖和项目

```bash
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
```

第一条命令安装第三方依赖。第二条以可编辑模式安装 DataPilot 本身，使 `src/datapilot` 可被导入，并注册 `datapilot` CLI 命令；`--no-deps` 用于避免重复解析依赖。

### 3. 创建配置文件

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

Linux/macOS：

```bash
cp .env.example .env
```

编辑 `.env`，至少填写模型 API Key：

```dotenv
OPENAI_API_KEY=your-api-key
DATAPILOT_MODEL_NAME=gpt-4.1-mini
```

如使用其他 OpenAI-compatible 服务，还需设置：

```dotenv
DATAPILOT_MODEL_BASE_URL=https://your-provider.example/v1
```

### 4. 初始化演示数据库

```bash
python scripts/seed_demo.py
```

成功后会生成 `data/demo.sqlite`，其中包含演示数据表 `sales`。

### 5. 启动 API

```bash
uvicorn datapilot.api:app --reload
```

启动后访问：

- Swagger API 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/health>
- 数据集列表：<http://127.0.0.1:8000/v1/datasets>

如端口被占用，可指定其他端口：

```bash
uvicorn datapilot.api:app --reload --port 8001
```

## 使用 API

以下 PowerShell 示例假设 API 运行在 `http://127.0.0.1:8000`。

### 查看可用数据集

```powershell
Invoke-RestMethod -Method Get `
  -Uri "http://127.0.0.1:8000/v1/datasets"
```

### 创建分析任务

```powershell
$body = @{
  dataset_id = "demo_sales"
  question   = "Analyze the monthly revenue trend"
  approved   = $false
} | ConvertTo-Json

$run = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs" `
  -ContentType "application/json" `
  -Body $body

$run
```

正常任务返回 `completed`。主要字段包括：

| 字段 | 含义 |
| --- | --- |
| `run_id` | 任务的唯一标识 |
| `dataset_id` | 使用的数据集 |
| `status` | 当前状态 |
| `report` | Markdown 分析报告 |
| `trace` | 各工作流节点的执行轨迹 |
| `artifacts` | 报告等产物的下载地址 |

### 查询已有任务

```powershell
Invoke-RestMethod -Method Get `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.run_id)"
```

### 下载报告

```powershell
Invoke-WebRequest `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.run_id)/artifacts/report" `
  -OutFile "report.md"
```

### 审批高风险任务

包含批量导出、删除、覆盖或外部发送等意图的请求会停在 `awaiting_approval` 状态。

```powershell
$body = @{
  dataset_id = "demo_sales"
  question   = "Export all customer records"
  approved   = $false
} | ConvertTo-Json

$riskRun = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs" `
  -ContentType "application/json" `
  -Body $body

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs/$($riskRun.run_id)/approve"
```

审批只允许工作流继续执行，不会提升数据库权限。SQL Runtime 始终拒绝数据修改操作。

## 使用 CLI

完成安装和演示数据库初始化后，可直接运行：

```bash
datapilot demo_sales "Analyze revenue by region"
```

显式批准高风险任务：

```bash
datapilot demo_sales "Export all customer records" --approved
```

CLI 会在终端输出报告，并将状态与报告保存到 `data/runs/`。

## 配置数据源

数据源统一登记在 `data/catalog.json`。API 请求只能提交 `dataset_id`，不能传入数据库连接字符串或临时修改表白名单。

### SQLite

```json
{
  "dataset_id": "demo_sales",
  "name": "Demo Sales Warehouse",
  "description": "Synthetic order-level sales data for local evaluation.",
  "driver": "sqlite",
  "database": "demo.sqlite",
  "allowed_tables": ["sales"]
}
```

相对数据库路径以 `catalog.json` 所在目录为基准。数据库文件必须已经存在。

### PostgreSQL

在 `data/catalog.json` 的 `datasets` 数组中添加：

```json
{
  "dataset_id": "production_sales",
  "name": "Production Sales Warehouse",
  "description": "Approved sales mart",
  "driver": "postgresql",
  "connection_env": "SALES_DATABASE_URL",
  "allowed_tables": ["orders", "order_items", "products"]
}
```

然后设置目录中指定的环境变量。

Windows PowerShell：

```powershell
$env:SALES_DATABASE_URL = "postgresql://readonly_user:password@host:5432/sales"
```

Linux/macOS：

```bash
export SALES_DATABASE_URL="postgresql://readonly_user:password@host:5432/sales"
```

修改目录或环境变量后需要重启 API。生产数据库账号应只拥有目标表或视图的 `SELECT` 权限。

## 业务语义层与混合检索

业务定义保存在 `data/semantic_catalog.json`。每条文档可描述指标、维度或业务规则：

```json
{
  "id": "metric.average_order_value",
  "kind": "metric",
  "name": "Average order value",
  "description": "Average gross revenue per order.",
  "table": "sales",
  "columns": ["revenue", "id"],
  "formula": "SUM(sales.revenue) / NULLIF(COUNT(sales.id), 0)",
  "aliases": ["AOV", "average revenue per order", "客单价"]
}
```

工作流在 SQL 生成前执行以下步骤：

1. 根据数据源白名单过滤不可用的表和字段；
2. 使用 BM25 计算关键词相关性；
3. 使用 Embedding 计算语义相关性；
4. 按配置权重融合分数并返回 Top-K；
5. 将受控公式和业务解释注入 SQL Agent。

Embedding 服务不可用时会退化为 BM25 检索，但 Planner 和 SQL Agent 仍必须调用大模型。

## MCP 工具服务

安装项目后启动 stdio MCP Server：

```bash
datapilot-mcp
```

提供四个工具：

| MCP 工具 | 作用 |
| --- | --- |
| `list_datasets` | 列出已登记数据集，不暴露连接字符串 |
| `get_schema` | 获取白名单内的表和字段 |
| `retrieve_business_context` | 检索指标、维度和业务规则 |
| `execute_readonly_sql` | 执行经过安全校验的单条只读 SQL |

MCP 客户端配置示例：

```json
{
  "mcpServers": {
    "datapilot": {
      "command": "datapilot-mcp",
      "args": []
    }
  }
}
```

MCP 只是工具协议入口，不会绕过 DataPilot 的目录白名单和 SQL 安全校验。

## 配置大模型

项目不提供本地规则降级模式。运行分析任务前必须配置支持结构化输出的 OpenAI-compatible 模型：

```dotenv
DATAPILOT_MODEL_NAME=gpt-4.1-mini
OPENAI_API_KEY=your-api-key
```

使用其他兼容服务时增加：

```dotenv
DATAPILOT_MODEL_NAME=your-model-name
DATAPILOT_MODEL_BASE_URL=https://your-provider.example/v1
OPENAI_API_KEY=your-provider-key
```

保存后重启 API。模型负责分析规划和 SQL 生成；风险审批、表白名单、只读校验、超时和结果行数限制由确定性代码执行。

## Docker 运行

确保 Docker Desktop 或 Docker Engine 已启动。

Windows PowerShell：

```powershell
Copy-Item .env.example .env
python scripts/seed_demo.py
docker compose up --build
```

Linux/macOS：

```bash
cp .env.example .env
python scripts/seed_demo.py
docker compose up --build
```

服务地址为 <http://127.0.0.1:8000>。停止服务：

```bash
docker compose down
```

Compose 会把本地 `data` 目录挂载到容器，因此任务状态和报告会保存在宿主机。

## 测试和评估

运行测试：

```bash
pytest
```

测试配置要求总覆盖率不低于 80%。

运行完整的 60 条中英文 Text-to-SQL 评估：

```bash
python scripts/seed_demo.py
python evaluation/run_eval.py
```

工作流评估会真实调用 `.env` 中配置的模型服务，因此会产生模型请求；单元测试使用注入式测试 Agent，不需要联网或 API Key。

首次验证可限制用例数量：

```bash
python evaluation/run_eval.py --limit 5
```

评估结果保存在 `evaluation/results.json`，包含：

- 任务成功率；
- SQL 执行成功率；
- 表选择准确率；
- 字段选择准确率；
- 语义检索命中率；
- 安全请求拦截率；
- 平均响应时间；
- 每条用例的状态、延迟、SQL 尝试次数和召回文档。

真实模型指标应以该文件的实际运行结果为准，不应在未运行评估时写入简历。

运行代码检查：

```bash
ruff check .
ruff format --check .
```

## 配置项

配置读取自 `.env` 或系统环境变量。

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATAPILOT_MODEL_NAME` | `gpt-4.1-mini` | 使用的模型名称 |
| `DATAPILOT_MODEL_BASE_URL` | 空 | 兼容服务地址；使用 OpenAI 时留空 |
| `DATAPILOT_MODEL_TEMPERATURE` | `0` | 模型生成温度 |
| `DATAPILOT_SQL_MAX_RETRIES` | `2` | SQL 失败后的最大修复次数 |
| `DATAPILOT_SEMANTIC_CATALOG_PATH` | `data/semantic_catalog.json` | 业务语义目录 |
| `DATAPILOT_EMBEDDING_MODEL` | `text-embedding-3-small` | 混合检索使用的向量模型 |
| `DATAPILOT_RETRIEVAL_TOP_K` | `5` | 注入 SQL Agent 的语义文档数 |
| `DATAPILOT_RETRIEVAL_VECTOR_WEIGHT` | `0.55` | 融合排序中的向量分数权重 |
| `OPENAI_API_KEY` | 空 | 模型服务 API Key，必填 |
| `DATAPILOT_EXECUTION_TIMEOUT_SECONDS` | `20` | 查询超时秒数 |
| `DATAPILOT_MAX_RESULT_ROWS` | `1000` | 单条查询最大返回行数 |
| `DATAPILOT_CATALOG_PATH` | `data/catalog.json` | 数据源目录路径 |
| `DATAPILOT_RUN_DIR` | `data/runs` | 状态和报告保存目录 |

## 项目结构

```text
DataPilot-Agent/
├── data/
│   ├── catalog.json           # 数据源目录
│   ├── semantic_catalog.json  # 指标、维度和业务口径
│   └── runs/                  # 任务状态和报告
├── evaluation/
│   ├── dataset.jsonl          # 评估用例
│   └── run_eval.py            # 评估入口
├── scripts/
│   └── seed_demo.py           # 演示数据库初始化
├── src/datapilot/
│   ├── agents/                # Planner、SQL、Analyst 等 Agent
│   ├── api.py                 # FastAPI 接口
│   ├── catalog.py             # 数据源目录
│   ├── datasources.py         # SQLite/PostgreSQL 访问
│   ├── retrieval.py           # BM25 + Embedding 混合检索
│   ├── mcp_server.py          # 受控 MCP 工具服务
│   ├── observability.py       # 模型 Token 用量采集
│   ├── security.py            # SQL 安全校验
│   ├── storage.py             # JSON 和 Markdown 持久化
│   └── workflow.py            # LangGraph 工作流
├── tests/
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── requirements.txt
```

## 常见问题

### 找不到 `datapilot` 命令

确认已经激活 Conda 环境并安装项目：

```bash
conda activate datapilot
python -m pip install -e . --no-deps
```

### 提示找不到 `data/demo.sqlite`

重新初始化演示数据：

```bash
python scripts/seed_demo.py
```

### 修改 `.env` 后没有生效

停止并重新启动 Uvicorn。环境配置在应用启动时加载。

### PostgreSQL 连接失败

检查：

1. `connection_env` 与实际环境变量名称是否一致；
2. 数据库地址是否可达；
3. 是否已为只读账号授予目标表的 `SELECT` 权限；
4. 表名是否已加入 `allowed_tables`。

## 当前边界

- 本地状态使用 JSON 文件保存，适合单实例演示，不适合多实例并发部署；
- 当前没有用户认证、租户隔离和行级权限；
- Agent 的分析质量受模型能力、Schema 描述和业务口径完整性影响；
- 报告结论来自查询证据，但不自动证明因果关系；
- 系统不执行邮件发送、批量导出或数据修改等外部副作用。

生产部署前应接入企业 IAM/RBAC、集中式状态存储、密钥管理、审计平台和更严格的数据库权限控制。
