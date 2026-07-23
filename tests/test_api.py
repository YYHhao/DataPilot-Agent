from fastapi.testclient import TestClient

import datapilot.api as api_module


def configured_client(enterprise_runtime, monkeypatch):
    catalog, store, workflow = enterprise_runtime
    monkeypatch.setattr(api_module, "catalog", catalog)
    monkeypatch.setattr(api_module, "store", store)
    monkeypatch.setattr(api_module, "workflow", workflow)
    return TestClient(api_module.app)


def test_health_and_catalog(enterprise_runtime, monkeypatch):
    client = configured_client(enterprise_runtime, monkeypatch)
    assert client.get("/health").json() == {"status": "ok"}
    datasets = client.get("/v1/datasets").json()
    assert datasets[0]["dataset_id"] == "test_sales"
    assert "database" not in datasets[0]


def test_api_creates_reads_and_downloads_run(enterprise_runtime, monkeypatch):
    client = configured_client(enterprise_runtime, monkeypatch)
    response = client.post(
        "/v1/runs",
        json={"dataset_id": "test_sales", "question": "Rank regions by revenue"},
    )
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "completed"
    assert client.get(f"/v1/runs/{run['run_id']}").status_code == 200
    report = client.get(run["artifacts"]["report"])
    assert report.status_code == 200
    assert "SQL evidence" in report.text


def test_api_approves_paused_run(enterprise_runtime, monkeypatch):
    client = configured_client(enterprise_runtime, monkeypatch)
    paused = client.post(
        "/v1/runs",
        json={"dataset_id": "test_sales", "question": "Delete source data"},
    ).json()
    assert paused["status"] == "awaiting_approval"
    resumed = client.post(f"/v1/runs/{paused['run_id']}/approve")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "completed"


def test_api_hides_unknown_resources(enterprise_runtime, monkeypatch):
    client = configured_client(enterprise_runtime, monkeypatch)
    response = client.post(
        "/v1/runs",
        json={"dataset_id": "unknown", "question": "Analyze"},
    )
    assert response.status_code == 404
    assert client.get("/v1/runs/not-a-run-id").status_code == 404
