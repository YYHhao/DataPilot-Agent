from __future__ import annotations

import json
import math
import re
from collections import Counter
from itertools import pairwise
from pathlib import Path

from pydantic import TypeAdapter

from datapilot.config import settings
from datapilot.models import RetrievedSemantic, SchemaProfile, SemanticDocument


def _tokens(text: str) -> list[str]:
    lowered = text.lower()
    words = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", lowered)
    chinese = [token for token in words if len(token) == 1 and "\u4e00" <= token <= "\u9fff"]
    bigrams = [left + right for left, right in pairwise(chinese)]
    return words + bigrams


def _document_text(document: SemanticDocument) -> str:
    return " ".join(
        [
            document.name,
            document.description,
            document.table,
            *document.columns,
            document.formula or "",
            *document.aliases,
        ]
    )


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


class SemanticRetriever:
    """Hybrid BM25 + embedding retrieval over governed business metadata."""

    def __init__(self, path: Path | None = None, embeddings=None) -> None:
        source = path or settings.semantic_catalog_path
        payload = json.loads(source.read_text(encoding="utf-8"))
        self.documents = TypeAdapter(list[SemanticDocument]).validate_python(payload["documents"])
        self._embeddings = embeddings
        self._document_vectors: list[list[float]] | None = None

    def retrieve(
        self,
        question: str,
        profile: SchemaProfile,
        top_k: int | None = None,
    ) -> list[RetrievedSemantic]:
        allowed_tables = {table.name for table in profile.tables}
        allowed_columns = {
            (table.name, column.name) for table in profile.tables for column in table.columns
        }
        candidates = [
            document
            for document in self.documents
            if document.table in allowed_tables
            and all((document.table, column) in allowed_columns for column in document.columns)
        ]
        if not candidates:
            return []

        lexical = self._bm25(question, candidates)
        vector = self._vector_scores(question, candidates)
        weight = settings.retrieval_vector_weight if vector else 0.0
        results = [
            RetrievedSemantic(
                document=document,
                lexical_score=round(lexical[index], 6),
                vector_score=round(vector[index], 6) if vector else 0.0,
                score=round(
                    (1 - weight) * lexical[index] + weight * (vector[index] if vector else 0.0),
                    6,
                ),
            )
            for index, document in enumerate(candidates)
        ]
        results.sort(key=lambda item: item.score, reverse=True)
        return results[: top_k or settings.retrieval_top_k]

    @staticmethod
    def _bm25(query: str, documents: list[SemanticDocument]) -> list[float]:
        tokenized = [_tokens(_document_text(document)) for document in documents]
        query_tokens = _tokens(query)
        lengths = [len(tokens) for tokens in tokenized]
        average_length = sum(lengths) / len(lengths) if lengths else 1
        document_frequency = Counter(token for tokens in tokenized for token in set(tokens))
        scores = []
        for tokens in tokenized:
            frequencies = Counter(tokens)
            score = 0.0
            for token in query_tokens:
                frequency = frequencies[token]
                if not frequency:
                    continue
                inverse_frequency = math.log(
                    1
                    + (len(documents) - document_frequency[token] + 0.5)
                    / (document_frequency[token] + 0.5)
                )
                denominator = frequency + 1.5 * (1 - 0.75 + 0.75 * len(tokens) / average_length)
                score += inverse_frequency * frequency * 2.5 / denominator
            scores.append(score)
        maximum = max(scores, default=0.0)
        return [score / maximum if maximum else 0.0 for score in scores]

    def _vector_scores(self, question: str, documents: list[SemanticDocument]) -> list[float]:
        try:
            embeddings = self._embeddings or self._create_embeddings()
            if self._document_vectors is None:
                self._document_vectors = embeddings.embed_documents(
                    [_document_text(document) for document in self.documents]
                )
            indexes = [self.documents.index(document) for document in documents]
            query_vector = embeddings.embed_query(question)
            raw = [_cosine(query_vector, self._document_vectors[index]) for index in indexes]
            minimum, maximum = min(raw), max(raw)
            return [
                (score - minimum) / (maximum - minimum) if maximum > minimum else 1.0
                for score in raw
            ]
        except Exception:  # noqa: BLE001 - embedding outages must fall back to lexical retrieval
            return []

    @staticmethod
    def _create_embeddings():
        from langchain_openai import OpenAIEmbeddings

        options = {"model": settings.embedding_model}
        if settings.openai_api_key:
            options["api_key"] = settings.openai_api_key.get_secret_value()
        if settings.model_base_url:
            options["base_url"] = settings.model_base_url
        return OpenAIEmbeddings(**options)
