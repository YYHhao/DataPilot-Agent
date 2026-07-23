FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY data/catalog.json ./data/catalog.json
RUN pip install --no-cache-dir .
RUN python scripts/seed_demo.py

RUN useradd --create-home --uid 10001 datapilot \
    && mkdir -p /app/data/runs \
    && chown -R datapilot:datapilot /app
USER datapilot

EXPOSE 8000
CMD ["uvicorn", "datapilot.api:app", "--host", "0.0.0.0", "--port", "8000"]
