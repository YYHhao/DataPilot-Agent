# DataPilot Agent

DataPilot Agent 是一个面向企业数据源的多 Agent 数据分析项目。用户提交已登记的 `dataset_id` 和自然语言问题后，系统会读取授权范围内的数据库结构、检索业务口径、生成并执行只读 SQL、复核查询证据，最后输出可追溯的中文 Markdown 报告。

项目当前支持 SQLite 和 PostgreSQL，提供 CLI、FastAPI 和 MCP 三种入口。Planner 与 Text-to-SQL Agent 通过 OpenAI-compatible 接口调用大模型；表白名单、SQL 只读校验、查询超时、结果行数限制和风险审批由确定性代码执行。

> 当前版本：`0.2.0`。本项目适合本地学习、功能验证和单实例原型演示，尚不是开箱即用的多租户生产平台。

## 一、项目结构

```text
DataPilot-Agent/
├── data/
│   ├── catalog.json                    # 数据集目录和表白名单
│   ├── semantic_catalog.json           # 指标、维度和业务规则
│   ├── olist_csv/                      # Olist 原始 CSV，不提交 Git
│   └── runs/                           # JSON 状态和 Markdown 报告
├── evaluation/
│   ├── dataset.jsonl                   # 评估用例
│   └── run_eval.py                     # 评估入口
├── scripts/
│   ├── seed_demo.py                    # SQLite 演示数据初始化
│   └── import_olist_postgres.py        # Olist PostgreSQL 导入脚本
├── src/datapilot/
│   ├── agents/                         # Planner、SQL、Analyst 等 Agent
│   ├── api.py                          # FastAPI 接口
│   ├── catalog.py                      # 数据集目录
│   ├── datasources.py                  # SQLite/PostgreSQL 访问
│   ├── retrieval.py                    # BM25 + Embedding 混合检索
│   ├── mcp_server.py                   # MCP 工具服务
│   ├── observability.py                # Token 用量采集
│   ├── security.py                     # SQL 安全校验
│   ├── storage.py                      # 状态和报告持久化
│   └── workflow.py                     # LangGraph 工作流
├── tests/
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── requirements.txt
```

## 二、核心能力

- 使用 LangGraph 编排 Planner、Schema、SQL、Analyst、Reviewer 和 Reporter；
- 使用结构化模型输出生成分析计划及 1～5 条分析 SQL；
- SQL 执行失败后，根据数据库错误自动生成修正计划；
- 使用 BM25 与 Embedding 混合检索指标、维度和业务规则；
- 支持 SQLite 与 PostgreSQL；
- 通过数据集目录和表白名单限制 Agent 可访问的数据；
- 只允许单条 `SELECT` 或 `WITH` 查询；
- 拒绝写操作、危险函数、SQL 注释和多语句；
- 限制查询时间和单次最大返回行数；
- 对删除、覆盖、批量导出和外部发送等高风险意图设置审批节点；
- 记录节点耗时、模型 Token、检索结果、SQL、错误和执行轨迹；
- 保存 JSON 任务状态与中文 Markdown 报告；
- 提供 FastAPI、CLI、MCP Server、Docker、测试和离线评估入口。

## 三、工作流程

```mermaid
flowchart TD
    U[自然语言问题和 dataset_id] --> P[Planner]
    P --> G{是否需要审批}
    G -->|需要且未批准| W[保存等待审批状态]
    G -->|不需要或已批准| S[Schema Agent]
    S --> K[业务语义混合检索]
    K --> Q[Text-to-SQL Agent]
    Q --> V[安全校验与只读执行]
    V --> E{执行成功}
    E -->|失败且可重试| F[SQL Repair Agent]
    F --> V
    E -->|成功或重试结束| A[Analyst]
    A --> R[Reviewer]
    R --> O[生成并保存报告]
```

| 组件 | 职责 |
| --- | --- |
| Planner | 判断分析类型并生成分析目标与步骤 |
| Schema Agent | 读取数据目录允许访问的表结构 |
| Semantic Retriever | 检索指标定义、维度说明和业务规则 |
| SQL Agent | 根据问题、Schema 和业务口径生成只读 SQL |
| SQL Repair Agent | 根据数据库错误或安全拒绝原因修复 SQL |
| SQL Runtime | 校验并以只读方式执行 SQL |
| Analyst | 将成功执行的查询整理为证据和发现 |
| Reviewer | 检查执行状态、数据权限和证据链 |
| Reporter | 生成包含 SQL、结果预览和复核结论的中文报告 |

## 四、环境要求

- Python `>=3.11,<3.15`；
- Miniconda、Anaconda 或其他 Python 虚拟环境；
- Windows PowerShell、Linux 或 macOS；
- Docker Desktop 或 Docker Engine，可选；
- PostgreSQL，可选，也可以通过 Docker 运行。

下文命令默认在项目根目录执行：

```text
D:\pythonDemo\agent\DataPilot-Agent
```

## 五、快速开始：SQLite 演示

这是验证 DataPilot 安装和模型配置的最短路径。

### 1. 创建并激活环境

```bash
conda create -n datapilot python=3.11 -y
conda activate datapilot
```

如果 `conda activate` 不可用，先执行 `conda init`，然后关闭并重新打开终端。

### 2. 安装依赖和项目

```bash
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
```

第二条命令以可编辑模式注册 `src/datapilot`，同时安装以下终端入口：

```text
datapilot
datapilot-mcp
```

代码仍保留在项目目录，修改源码后通常不需要重新安装。

### 3. 创建模型配置

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

Linux 或 macOS：

```bash
cp .env.example .env
```

编辑 `.env`：

```dotenv
OPENAI_API_KEY=your-api-key
DATAPILOT_MODEL_NAME=your-model-name
DATAPILOT_MODEL_BASE_URL=https://your-provider.example/v1
```

使用 OpenAI 官方接口时，可将 `DATAPILOT_MODEL_BASE_URL` 留空。模型必须兼容 OpenAI Chat Completions，并支持结构化输出。

### 4. 初始化演示数据

```bash
python scripts/seed_demo.py
```

该命令生成 `data/demo.sqlite`，其中包含 `sales` 演示表。

### 5. 运行 CLI

```bash
datapilot demo_sales "按地区分析销售收入并从高到低排序"
```

CLI 会在终端输出报告，并将任务状态和报告保存到 `data/runs/`。

如果提示找不到 `datapilot`，确认提示符中已经出现 `(datapilot)`，然后重新执行：

```bash
python -m pip install -e . --no-deps
```

### 6. 启动 API

此步骤是可选的。如果只通过 `datapilot` CLI 在终端运行分析任务，不需要启动 API；当需要使用 Swagger 调试接口、让网页前端或其他程序通过 HTTP 调用 DataPilot、查询任务状态、审批任务或下载报告时，才需要启动 API。

```bash
uvicorn datapilot.api:app --reload
```

启动后访问：

- Swagger 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/health>
- 数据集列表：<http://127.0.0.1:8000/v1/datasets>

访问根地址 `/` 返回 `404` 属于正常现象；当前项目没有定义首页路由。

## 六、Olist + PostgreSQL 完整示例

项目已提供 Olist CSV 导入脚本，适合测试多表 JOIN、月度趋势、商品类别、客户地区、支付方式、配送时效和评价分析。

### 1. 准备 CSV

将 Olist 文件放入：

```text
data/olist_csv/
├── olist_customers_dataset.csv
├── olist_geolocation_dataset.csv
├── olist_order_items_dataset.csv
├── olist_order_payments_dataset.csv
├── olist_order_reviews_dataset.csv
├── olist_orders_dataset.csv
├── olist_products_dataset.csv
├── olist_sellers_dataset.csv
└── product_category_name_translation.csv
```

该目录已被 `.gitignore` 忽略，避免误提交大型数据文件。

### 2. 使用 Docker 创建 PostgreSQL

确保 Docker Desktop 已启动：

```powershell
docker pull postgres:17

docker run --name olist-postgres `
  -e POSTGRES_USER=postgres `
  -e POSTGRES_PASSWORD=your-admin-password `
  -e POSTGRES_DB=olist `
  -p 5432:5432 `
  -v olist_postgres_data:/var/lib/postgresql/data `
  --restart unless-stopped `
  -d postgres:17
```

检查容器：

```powershell
docker ps
docker logs olist-postgres
```

日志出现 `database system is ready to accept connections` 表示数据库已经启动。

### 3. 导入 Olist CSV

确保已经安装 PostgreSQL 驱动：

```powershell
python -m pip install "psycopg[binary]>=3.2,<4"
```

在当前 PowerShell 设置管理员连接地址：

```powershell
$env:OLIST_ADMIN_DATABASE_URL = "postgresql://postgres:your-admin-password@localhost:5432/olist"
```

执行导入：

```powershell
python scripts/import_olist_postgres.py
```

脚本会创建9张表、批量导入 CSV、创建常用索引并执行 `ANALYZE`。如果已有同名表且需要重新导入：

```powershell
python scripts/import_olist_postgres.py --replace
```

`--replace` 会删除并重建 Olist 同名表，仅在确认需要重新导入时使用。

### 4. 创建只读账户

```powershell
docker exec -it olist-postgres psql -U postgres -d olist
```

在 `psql` 中执行：

```sql
CREATE USER datapilot_reader WITH PASSWORD 'your-reader-password';

GRANT CONNECT ON DATABASE olist TO datapilot_reader;
GRANT USAGE ON SCHEMA public TO datapilot_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO datapilot_reader;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO datapilot_reader;

ALTER ROLE datapilot_reader SET default_transaction_read_only = on;
ALTER ROLE datapilot_reader SET statement_timeout = '20s';
```

退出：

```sql
\q
```

### 5. 配置并测试连接

`data/catalog.json` 已登记 `olist` 数据集。运行 CLI 前，在同一个 PowerShell 设置只读连接：

```powershell
$env:OLIST_DATABASE_URL = "postgresql://datapilot_reader:your-reader-password@localhost:5432/olist"
```

运行：

```powershell
datapilot olist "分析数据集中全部历史月份的订单数量和销售收入变化"
```

Olist 数据主要是历史数据。DataPilot 会把用户原始问题传给 SQL Agent；当用户没有提出相对时间范围时，安全层会拒绝模型擅自生成的 `CURRENT_DATE`、`NOW()` 等相对当前时间条件，并触发 SQL 修复。若确实需要最近24个月，应在问题中明确说明。

管理员变量 `OLIST_ADMIN_DATABASE_URL` 只用于数据导入；日常分析应使用权限受限的 `OLIST_DATABASE_URL`。

### 6. Docker 常用命令

```powershell
docker stop olist-postgres
docker start olist-postgres
docker ps -a --filter "name=olist-postgres"
```

数据库保存在 Docker volume `olist_postgres_data` 中，停止容器不会删除数据。

## 七、使用 CLI

基本格式：

```bash
datapilot <dataset_id> "<自然语言问题>"
```

示例：

```bash
datapilot demo_sales "分析各地区的销售收入"
datapilot olist "按商品类别统计销售额最高的十个类别"
datapilot olist "比较各支付方式的订单量和平均支付金额"
```

显式批准高风险请求：

```bash
datapilot demo_sales "导出全部客户记录" --approved
```

审批只允许工作流继续运行，不会提升数据库权限，也不会绕过只读 SQL 校验。

## 八、使用 API

### 查看数据集

```powershell
Invoke-RestMethod -Method Get `
  -Uri "http://127.0.0.1:8000/v1/datasets"
```

### 创建分析任务

```powershell
$body = @{
  dataset_id = "demo_sales"
  question   = "按地区分析销售收入"
  approved   = $false
} | ConvertTo-Json

$run = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs" `
  -ContentType "application/json" `
  -Body $body

$run
```

主要响应字段：

| 字段 | 含义 |
| --- | --- |
| `run_id` | 任务唯一标识 |
| `dataset_id` | 使用的数据集 |
| `status` | 当前工作流状态 |
| `report` | 中文 Markdown 报告 |
| `trace` | 节点执行轨迹、耗时和模型 Token |
| `artifacts` | 报告下载地址 |

### 查询任务和下载报告

```powershell
Invoke-RestMethod -Method Get `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.run_id)"

Invoke-WebRequest `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.run_id)/artifacts/report" `
  -OutFile "report.md"
```

### 审批任务

当任务状态为 `awaiting_approval` 时：

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.run_id)/approve"
```

## 九、数据源目录

数据源登记在 `data/catalog.json`。客户端只能提交 `dataset_id`，不能在请求中传入连接字符串或临时修改表白名单。

### SQLite

```json
{
  "dataset_id": "demo_sales",
  "name": "演示销售数据仓库",
  "description": "用于本地演示和评估的合成订单级销售数据。",
  "driver": "sqlite",
  "database": "demo.sqlite",
  "allowed_tables": ["sales"]
}
```

相对数据库路径以 `catalog.json` 所在目录为基准。

### PostgreSQL

```json
{
  "dataset_id": "production_sales",
  "name": "生产销售数据集",
  "description": "经过授权的销售分析数据。",
  "driver": "postgresql",
  "connection_env": "SALES_DATABASE_URL",
  "allowed_tables": ["orders", "order_items", "products"]
}
```

本地 PowerShell 设置连接变量：

```powershell
$env:SALES_DATABASE_URL = "postgresql://readonly_user:password@localhost:5432/sales"
```

当前 PostgreSQL 数据源通过 `os.getenv()` 读取 `connection_env` 指定的变量。因此本地 CLI 运行时，需要在启动命令的同一终端设置连接变量；仅把自定义数据库变量写入 `.env` 不一定会进入当前进程环境。Docker Compose 的 `env_file` 会将 `.env` 变量注入容器。

生产数据库应使用只读账户，并仅授予白名单表或视图的 `SELECT` 权限。

## 十、业务语义目录

业务定义保存在 `data/semantic_catalog.json`。每条文档描述一个指标、维度或业务规则：

```json
{
  "id": "metric.average_order_value",
  "kind": "metric",
  "name": "平均客单价",
  "description": "每个订单的平均销售总收入。",
  "table": "sales",
  "columns": ["revenue", "id"],
  "formula": "SUM(sales.revenue) / NULLIF(COUNT(sales.id), 0)",
  "aliases": ["AOV", "average revenue per order", "客单价"]
}
```

检索过程：

1. 按当前数据集表白名单过滤语义文档；
2. 使用 BM25 计算关键词相关性；
3. 使用 Embedding 计算语义相关性；
4. 融合分数并返回 Top-K；
5. 将受控公式和业务解释注入 SQL Agent。

Embedding 服务不可用时会退化为 BM25，但 Planner 和 SQL Agent 仍需要可用的大模型服务。新增数据集时，应同步补充该数据集的指标和业务规则，否则报告会显示“未找到与请求匹配的受治理业务定义”。当前目录已包含 Olist 的订单量、商品收入、支付金额、客单价、运费、评价分、订单月份、订单状态、商品类别和完整历史范围规则。

## 十一、MCP Server

启动 stdio MCP Server：

```bash
datapilot-mcp
```

提供以下工具：

| 工具 | 作用 |
| --- | --- |
| `list_datasets` | 列出已登记数据集，不暴露数据库凭据 |
| `get_schema` | 获取白名单中的表和字段 |
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

## 十二、Docker 运行 DataPilot API

项目根目录已有 `Dockerfile` 和 `docker-compose.yml`：

```powershell
Copy-Item .env.example .env
python scripts/seed_demo.py
docker compose up --build
```

服务地址：<http://127.0.0.1:8000>。

停止：

```powershell
docker compose down
```

Compose 会把本地 `data` 目录挂载到容器，因此任务状态和报告保存在宿主机。若 DataPilot API 也运行在容器中，连接另一个 PostgreSQL 容器时不能使用 `localhost`；应将两个服务加入同一 Docker 网络，并使用 PostgreSQL 服务名作为主机名。

## 十三、配置项

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `OPENAI_API_KEY` | 空 | 模型服务密钥，运行分析任务前必须配置 |
| `DATAPILOT_MODEL_NAME` | `gpt-4.1-mini` | 模型名称 |
| `DATAPILOT_MODEL_BASE_URL` | 空 | OpenAI-compatible 服务地址 |
| `DATAPILOT_MODEL_TEMPERATURE` | `0` | 模型生成温度 |
| `DATAPILOT_SQL_MAX_RETRIES` | `2` | SQL 失败后的最大修复次数 |
| `DATAPILOT_SEMANTIC_CATALOG_PATH` | `data/semantic_catalog.json` | 业务语义目录 |
| `DATAPILOT_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding 模型名称 |
| `DATAPILOT_RETRIEVAL_TOP_K` | `5` | 注入 SQL Agent 的语义文档数 |
| `DATAPILOT_RETRIEVAL_VECTOR_WEIGHT` | `0.55` | 混合检索中的向量权重 |
| `DATAPILOT_EXECUTION_TIMEOUT_SECONDS` | `20` | SQL 查询超时秒数 |
| `DATAPILOT_MAX_RESULT_ROWS` | `1000` | 单条查询最大返回行数 |
| `DATAPILOT_CATALOG_PATH` | `data/catalog.json` | 数据集目录 |
| `DATAPILOT_RUN_DIR` | `data/runs` | 任务状态和报告目录 |

## 十四、测试与评估

运行完整测试：

```bash
pytest
```

项目要求总测试覆盖率不低于 80%。单元测试使用注入式测试 Agent，不需要联网或 API Key。

运行 Text-to-SQL 评估：

```bash
python scripts/seed_demo.py
python evaluation/run_eval.py
```

首次验证可以限制用例数量：

```bash
python evaluation/run_eval.py --limit 5
```

评估会真实调用已配置的模型服务，结果写入 `evaluation/results.json`。

运行聚焦业务效果的评测（结果级 Text-to-SQL 正确率、SQL Repair 修复成功率、
安全拦截率以及 P50/P95 时延）：

```bash
python evaluation/run_business_eval.py
```

首次验证模型连接时可减少在线调用数量：

```bash
python evaluation/run_business_eval.py --limit 2 --repair-limit 1
```

该评测会在同一数据库上分别执行模型 SQL 和标准 SQL，通过有序结果集等价判断
Text-to-SQL 与 Repair 是否正确；安全评测同时报告攻击拦截率和正常查询放行率。
完整结果写入 `evaluation/business_results.json`。

代码检查：

```bash
ruff check .
ruff format --check .
```

## 十五、常见问题

### `datapilot` 命令不存在

```powershell
conda activate datapilot
python -m pip install -e . --no-deps
Get-Command datapilot
```

### `ModuleNotFoundError: No module named 'datapilot'`

项目采用 `src` 布局。推荐执行：

```bash
python -m pip install -e . --no-deps
```

临时启动 API 也可以使用：

```bash
python -m uvicorn datapilot.api:app --reload --app-dir src
```

### 模型提示 `Missing credentials`

确认 `.env` 中存在有效的：

```dotenv
OPENAI_API_KEY=your-api-key
```

修改配置后重启 CLI 或 Uvicorn。

### 提示设置 `OLIST_ADMIN_DATABASE_URL`

导入 Olist 前在当前 PowerShell 执行：

```powershell
$env:OLIST_ADMIN_DATABASE_URL = "postgresql://postgres:your-admin-password@localhost:5432/olist"
```

### PostgreSQL 连接失败

依次检查：

1. `docker ps` 中 `olist-postgres` 是否为 `Up`；
2. `connection_env` 与实际环境变量名是否一致；
3. 数据库地址、端口、用户名和密码是否正确；
4. 是否安装 `psycopg[binary]`；
5. 只读账户是否拥有 Schema 的 `USAGE` 和目标表的 `SELECT` 权限；
6. 表名是否位于 `allowed_tables` 中。

### 报告中的查询返回0行

先查看报告里的实际 SQL。常见原因包括：

- 模型添加了不适用于历史数据的“最近 N 个月”条件；
- 时间范围不覆盖数据集实际年份；
- `INNER JOIN` 没有匹配记录；
- 状态值或类别值与数据库实际内容不一致。

当所有查询均成功执行但全部返回0行时，Reviewer 会将任务标记为 `quality_gate_failed`，避免把无证据报告误判为完成。

对 Olist 可先验证：

```sql
SELECT COUNT(*), MIN(order_purchase_timestamp), MAX(order_purchase_timestamp)
FROM orders;
```

然后在问题中明确“使用全部历史数据，不要按当前日期过滤”。

### LangChain 或 Pydantic 警告

依赖库的弃用或序列化警告通常不会阻止任务执行。应优先查看异常栈最后一段，以及任务 JSON 中的 `status`、`query_results` 和 `trace`。

## 十六、当前边界

- 任务状态使用本地 JSON 文件保存，不适合多实例并发写入；
- 尚未提供用户认证、租户隔离、RBAC 和行级权限；
- Agent 的分析质量依赖模型、Schema 描述和业务语义目录的完整性；
- SQL 执行成功不等于业务结论正确；系统会阻止未被用户要求的相对时间范围，并在全部查询返回0行时令质量门禁失败，但其他口径错误仍需要评估与人工复核；
- 报告中的结果来自只读查询证据，但不能自动证明因果关系；
- 系统不会真正发送邮件、批量导出或执行数据库修改；
- Swagger 是开发调试界面，不是最终用户聊天前端。

生产部署前应增加企业 IAM/RBAC、集中式状态存储、密钥管理、审计平台、连接池、任务队列、行列级权限和更严格的质量门禁。
