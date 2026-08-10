from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from datapilot.catalog import DatasetCatalog
from datapilot.config import settings
from datapilot.models import DatasetResponse, RunRequest, RunResponse
from datapilot.storage import JsonRunStore
from datapilot.workflow import DataPilotWorkflow


app = FastAPI(
    title="DataPilot 企业数据分析智能体",
    version="0.2.0",
    description="面向目录授权数据源、具备安全治理能力的自然语言数据分析服务。",
)
catalog = DatasetCatalog(settings.catalog_path)
store = JsonRunStore(settings.run_dir)
workflow = DataPilotWorkflow(catalog, store)


def _response(state: dict) -> RunResponse:
    return RunResponse(
        run_id=state["run_id"],
        dataset_id=state["dataset_id"],
        status=state["status"],
        report=state.get("report"),
        trace=state.get("trace", []),
        artifacts=state.get("artifacts", {}),
    )


@app.get("/health", summary="健康检查", description="检查 DataPilot 服务是否正常运行。")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/datasets", response_model=list[DatasetResponse], summary="列出数据集")
def list_datasets() -> list[DatasetResponse]:
    return [
        DatasetResponse(
            dataset_id=item.dataset_id,
            name=item.name,
            description=item.description,
            driver=item.driver,
            allowed_tables=item.allowed_tables,
        )
        for item in catalog.list()
    ]


@app.post("/v1/runs", response_model=RunResponse, summary="创建分析任务")
def create_run(request: RunRequest) -> RunResponse:
    try:
        return _response(workflow.run(request.dataset_id, request.question, request.approved))
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/v1/runs/{run_id}", response_model=RunResponse, summary="查询分析任务")
def get_run(run_id: str) -> RunResponse:
    try:
        return _response(store.load(run_id))
    except KeyError as exc:
        raise HTTPException(404, "未找到分析任务") from exc


@app.post("/v1/runs/{run_id}/approve", response_model=RunResponse, summary="批准分析任务")
def approve_run(run_id: str) -> RunResponse:
    try:
        return _response(workflow.approve(run_id))
    except KeyError as exc:
        raise HTTPException(404, "未找到分析任务") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/v1/runs/{run_id}/artifacts/report", summary="下载分析报告")
def download_report(run_id: str) -> FileResponse:
    try:
        path = store.report_path(run_id)
    except KeyError as exc:
        raise HTTPException(404, "未找到分析报告") from exc
    return FileResponse(path, media_type="text/markdown; charset=utf-8", filename=f"{run_id}.md")
