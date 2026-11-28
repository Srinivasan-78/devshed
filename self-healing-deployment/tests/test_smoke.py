"""Smoke and unit tests for self-healing-deployment."""
import importlib
import json
import pathlib
import sys

from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "healthcheck"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "app"))

CLOSED = "http://127.0.0.1:9/"  # discard port, nothing listening


def test_modules_import():
    importlib.import_module("validate")
    importlib.import_module("log_event")


def test_check_once_reports_unreachable_host_as_not_ok():
    validate = importlib.import_module("validate")
    res = validate.check_once(CLOSED, 0.5)
    assert res["ok"] is False
    assert res["http_status"] is None
    assert "error" in res


def test_validate_gives_up_after_the_configured_retries():
    validate = importlib.import_module("validate")
    out = validate.validate(CLOSED, retries=3, delay=0, timeout=0.5, max_ms=1000)
    assert out["healthy"] is False
    assert len(out["attempts"]) == 3
    assert all(a["ok"] is False for a in out["attempts"])


def test_app_endpoints(monkeypatch):
    app_mod = importlib.import_module("main")
    client = TestClient(app_mod.app)

    assert client.get("/").status_code == 200
    assert client.get("/version").status_code == 200
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

    monkeypatch.setattr(app_mod, "FORCE_FAIL", True)
    failing = client.get("/health")
    assert failing.status_code == 500


def test_log_event_appends_json_array(tmp_path, monkeypatch):
    log_event = importlib.import_module("log_event")
    log_file = tmp_path / "deployments.json"
    monkeypatch.setattr(sys, "argv", ["log_event.py", "--status", "success", "--version", "v1", "--log-path", str(log_file)])
    log_event.main()
    monkeypatch.setattr(sys, "argv", ["log_event.py", "--status", "rollback", "--version", "v2", "--log-path", str(log_file), "--reason", "health_check_failed"])
    log_event.main()
    entries = json.loads(log_file.read_text(encoding="utf-8"))
    assert len(entries) == 2
    assert entries[0]["status"] == "success"
    assert entries[1]["status"] == "rollback"
    assert entries[1]["reason"] == "health_check_failed"
