from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnalysisType(StrEnum):
    OVERVIEW = "overview"
    DATA_QUALITY = "data_quality"
    RANKING = "ranking"
    TREND = "trend"
    CORRELATION = "correlation"


class DatasetDefinition(BaseModel):
    dataset_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    name: str
    description: str = ""
    driver: Literal["sqlite", "postgresql"]
    database: str | None = None
    connection_env: str | None = None
    allowed_tables: list[str] = Field(min_length=1)


class ColumnSchema(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    primary_key: bool = False


class TableSchema(BaseModel):
    name: str
    columns: list[ColumnSchema]


class SchemaProfile(BaseModel):
    dataset_id: str
    dataset_name: str
    description: str
    driver: str
    tables: list[TableSchema]


class SemanticDocument(BaseModel):
    id: str
    kind: Literal["metric", "dimension", "business_rule"]
    name: str
    description: str
    table: str
    columns: list[str]
    formula: str | None = None
    aliases: list[str] = Field(default_factory=list)


class RetrievedSemantic(BaseModel):
    document: SemanticDocument
    score: float
    lexical_score: float
    vector_score: float


class AnalysisPlan(BaseModel):
    objective: str
    analysis_type: AnalysisType = AnalysisType.OVERVIEW
    steps: list[str]
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    risk_reasons: list[str] = Field(default_factory=list)


class SqlQuery(BaseModel):
    query_id: str = Field(pattern=r"^Q[1-9][0-9]*$")
    purpose: str
    sql: str


class SqlQueryPlan(BaseModel):
    dialect: Literal["sqlite", "postgresql"]
    queries: list[SqlQuery] = Field(min_length=1, max_length=5)


class ReviewResult(BaseModel):
    passed: bool
    score: float = Field(ge=0, le=1)
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    checked_evidence: list[str] = Field(default_factory=list)


class RunRequest(BaseModel):
    dataset_id: str
    question: str = Field(min_length=1, max_length=2_000)
    approved: bool = False


class RunResponse(BaseModel):
    run_id: str
    dataset_id: str
    status: str
    report: str | None = None
    trace: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)


class DatasetResponse(BaseModel):
    dataset_id: str
    name: str
    description: str
    driver: str
    allowed_tables: list[str]


class AgentState(TypedDict, total=False):
    run_id: str
    created_at: str
    dataset_id: str
    question: str
    approved: bool
    plan: dict[str, Any]
    schema_profile: dict[str, Any]
    semantic_context: list[dict[str, Any]]
    sql_plan: dict[str, Any]
    sql_attempt: int
    query_results: list[dict[str, Any]]
    analysis: dict[str, Any]
    review: dict[str, Any]
    report: str
    status: str
    trace: list[dict[str, Any]]
    artifacts: dict[str, str]


def new_state(run_id: str, dataset_id: str, question: str, approved: bool) -> AgentState:
    return {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "question": question,
        "approved": approved,
        "status": "created",
        "trace": [],
        "artifacts": {},
    }
