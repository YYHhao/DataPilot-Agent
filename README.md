# DataPilot Enterprise Data Analysis Agent

DataPilot 是一个面向企业数据库的多 Agent 数据分析项目。用户提交自然语言问题和
`dataset_id`，系统在受控数据源目录的权限边界内完成：

1. 分析意图与风险判断；
2. 数据库 Schema 检索；
3. Text-to-SQL 查询规划；
4. SQL 安全检查与只读执行；
5. 证据整理和独立复核；
6. 生成可追溯的 Markdown 报告。

项目默认使用确定性规则运行，不需要 API Key；也可以配置 OpenAI 模型驱动 Planner
和 SQL Agent。

## 系统架构

```mermaid
flowchart TD
    U[Question + dataset_id] --> P[Planner Agent]
    P -->|高风险| H[Approval Gate]
    H -->|等待审批| X[Persist]
    H -->|已批准| S[Schema Agent]
    P -->|低风险| S
    S --> Q[SQL Agent]
    Q --> G[SQL Security Gate]
    G -->|通过| D[(Read-only Database)]
    G -->|拒绝| R[Reviewer Agent]
    D --> A[Analyst Agent]
    A --> R
    R --> W[Reporter]
    W --> X
```

| 组件 | 作用 | 数据库权限 |
| --- | --- | --- |
| Planner | 识别分析类型、步骤和风险 | 无 |
| Schema Agent | 检查目录允许的表结构 | 只读 Schema |
| SQL Agent | 生成结构化 SQL 查询计划 | 无 |
| Security Gate | 检查语句类型和表权限 | 无 |
| SQL Runtime | 执行有界查询 | 只读 |
| Analyst | 从查询结果提取带证据编号的发现 | 无 |
| Reviewer | 检查查询状态、权限和证据血缘 | 无 |
| Reporter | 生成 Markdown 报告 | 无 |

## 支持的能力

- SQLite 本地演示数据源；
- PostgreSQL 企业数据源；
- 数据源目录和表级白名单；
- 排名、趋势、数据质量、相关性和概览分析；
- SQL 只读校验、危险函数拒绝和最大结果行数限制；
- PostgreSQL 只读事务与查询超时；
- 高风险请求暂停和人工审批；
- 节点级执行轨迹；
- JSON 运行状态和 Markdown 报告持久化；
- FastAPI、CLI、Docker、pytest 和离线评测。

## 环境要求

- Python 3.11–3.14
- Windows PowerShell、Linux 或 macOS
- Docker 可选
- PostgreSQL 可选

## 本地运行

下面的步骤使用项目自带的 SQLite 演示数据库，不需要 OpenAI API Key。

### Windows PowerShell：首次运行

进入项目目录：

```powershell
cd D:\pythonDemo\agent\DataPilot-Agent
```

创建并激活虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 禁止执行激活脚本，可仅对当前终端临时放行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

安装项目和开发依赖：

```powershell
python -m pip install -e ".[dev]"
```

复制配置并生成演示数据库：

```powershell
Copy-Item .env.example .env
python scripts\seed_demo.py
```

启动 API：

```powershell
uvicorn datapilot.api:app --reload
```

启动成功后访问：

- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`
- 数据源目录：`http://127.0.0.1:8000/v1/datasets`

### Linux/macOS：首次运行

```bash
cd DataPilot-Agent
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
python scripts/seed_demo.py
uvicorn datapilot.api:app --reload
```

### 日常启动

首次初始化完成后，不需要重新创建虚拟环境或安装依赖：

```powershell
cd D:\pythonDemo\agent\DataPilot-Agent
.\.venv\Scripts\Activate.ps1
uvicorn datapilot.api:app --reload
```

如果删除了 `data/demo.sqlite`，重新执行：

```powershell
python scripts\seed_demo.py
```

## 调用 API

### 查看注册的数据源

PowerShell：

```powershell
Invoke-RestMethod -Method Get `
  -Uri "http://127.0.0.1:8000/v1/datasets"
```

### 创建分析任务

PowerShell：

```powershell
$body = @{
  dataset_id = "demo_sales"
  question   = "分析每月销售收入趋势"
  approved   = $false
} | ConvertTo-Json

$run = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs" `
  -ContentType "application/json" `
  -Body $body

$run
```

Bash：

```bash
curl -X POST http://127.0.0.1:8000/v1/runs \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "demo_sales",
    "question": "Analyze the monthly revenue trend",
    "approved": false
  }'
```

任务成功后主要返回：

```json
{
  "run_id": "0123456789abcdef0123456789abcdef",
  "dataset_id": "demo_sales",
  "status": "completed",
  "report": "# Enterprise Data Analysis Report\n...",
  "trace": [],
  "artifacts": {
    "report": "/v1/runs/0123456789abcdef0123456789abcdef/artifacts/report"
  }
}
```

### 查询任务

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

包含删除、覆盖、批量导出或外部发送等意图的请求会返回
`awaiting_approval`：

```powershell
$riskBody = @{
  dataset_id = "demo_sales"
  question   = "Export all customer records"
  approved   = $false
} | ConvertTo-Json

$riskRun = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs" `
  -ContentType "application/json" `
  -Body $riskBody

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs/$($riskRun.run_id)/approve"
```

审批不会提升数据库权限。SQL Runtime 始终拒绝写操作。

## 使用 CLI

完成安装和演示数据初始化后：

```powershell
datapilot demo_sales "分析各地区销售收入排名"
```

高风险任务可以显式批准：

```powershell
datapilot demo_sales "Export all customer records" --approved
```

CLI 会将报告输出到终端，同时将运行状态和报告保存到 `data/runs/`。

## 数据源配置

数据源目录位于 [data/catalog.json](data/catalog.json)。API 客户端只能提交
`dataset_id`，不能提交或覆盖数据库连接串。

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

SQLite 的相对路径以 `catalog.json` 所在目录为基准。

### PostgreSQL

在 `data/catalog.json` 中添加：

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

安装 PostgreSQL 依赖：

```powershell
python -m pip install -e ".[postgres]"
```

设置目录中指定的连接环境变量：

```powershell
$env:SALES_DATABASE_URL = "postgresql://readonly_user:password@host:5432/sales"
```

然后重启 API。生产数据库账号应只拥有目标表或视图的 `SELECT` 权限。

## 启用 OpenAI Agent

默认 `.env` 使用：

```dotenv
DATAPILOT_MODEL_PROVIDER=mock
```

该模式使用确定性规则生成分析计划，方便离线运行和测试。

安装 OpenAI 可选依赖：

```powershell
python -m pip install -e ".[openai]"
```

修改 `.env`：

```dotenv
DATAPILOT_MODEL_PROVIDER=openai
DATAPILOT_MODEL_NAME=gpt-4.1-mini
OPENAI_API_KEY=your-api-key
```

重启 API：

```powershell
uvicorn datapilot.api:app --reload
```

模型生成的 SQL 仍然必须通过独立安全门，并且只能使用目录允许的数据表。

## Docker 运行

Docker Desktop 或 Docker Engine 必须处于运行状态。

PowerShell：

```powershell
Copy-Item .env.example .env
python scripts\seed_demo.py
docker compose up --build
```

Linux/macOS：

```bash
cp .env.example .env
python scripts/seed_demo.py
docker compose up --build
```

停止服务：

```bash
docker compose down
```

Compose 将本地 `data` 目录挂载到容器的 `/app/data`，因此运行记录保留在宿主机。

## 测试和评测

确保开发依赖已经安装：

```powershell
python -m pip install -e ".[dev]"
python scripts\seed_demo.py
```

运行完整测试：

```powershell
pytest
```

运行内置工作流评测：

```powershell
python evaluation\run_eval.py
```

运行静态检查和格式检查：

```powershell
ruff check .
ruff format --check .
```

当前测试覆盖 API、完整工作流、审批恢复、SQL 安全、数据源目录、Agent 规划及报告
持久化。内置评测验证排名、趋势和安全审批路径。

## 配置项

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATAPILOT_MODEL_PROVIDER` | `mock` | `mock` 或 `openai` |
| `DATAPILOT_MODEL_NAME` | `gpt-4.1-mini` | Planner 和 SQL Agent 模型 |
| `DATAPILOT_EXECUTION_TIMEOUT_SECONDS` | `20` | 数据库查询超时 |
| `DATAPILOT_MAX_RESULT_ROWS` | `1000` | 单条查询最大返回行数 |
| `DATAPILOT_CATALOG_PATH` | `data/catalog.json` | 数据源目录 |
| `DATAPILOT_RUN_DIR` | `data/runs` | 状态和报告目录 |

## 项目结构

```text
DataPilot-Agent/
├── data/
│   ├── catalog.json
│   └── runs/
├── evaluation/
│   ├── dataset.jsonl
│   └── run_eval.py
├── scripts/
│   └── seed_demo.py
├── src/datapilot/
│   ├── agents/
│   ├── api.py
│   ├── catalog.py
│   ├── datasources.py
│   ├── security.py
│   ├── storage.py
│   └── workflow.py
├── tests/
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## 当前边界

- 本地运行状态使用 JSON 文件，适合单实例演示；
- 多副本部署应替换为 PostgreSQL Checkpointer 和对象存储；
- 当前没有用户认证、租户隔离和行级权限；
- OpenAI 模式需要自行提供 API Key；
- 当前 Reporter 不执行批量导出、发送邮件或数据修改操作。

这些限制需要在生产部署前结合企业 IAM、RBAC、审计平台和密钥管理系统解决。
