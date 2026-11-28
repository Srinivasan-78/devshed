import os
import sys
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")
os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

API_ROOT = Path(__file__).resolve().parents[1] / "api"
sys.path.insert(0, str(API_ROOT))

from app import create_app  # noqa: E402
from app.free_tier import (  # noqa: E402
    IMPLEMENTED_PROVIDERS,
    SUPPORTED_PROVIDERS,
    normalize_provider,
    validate_spec,
)


def test_free_tier_allowlist():
    assert normalize_provider(" AWS ") == "aws"
    assert "aws" in IMPLEMENTED_PROVIDERS
    assert "gcp" in IMPLEMENTED_PROVIDERS
    assert "azure" in SUPPORTED_PROVIDERS
    assert "oracle" in SUPPORTED_PROVIDERS

    spec = validate_spec("aws")
    assert spec["instance_type"] == "t3.micro"
    assert spec["region"] == "us-east-1"


def test_app_health_and_login_validation():
    app = create_app()
    client = app.test_client()

    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}

    bad_email = client.post("/login", data={"email": "not-an-email", "password": "password123"})
    assert bad_email.status_code == 400

    short_pw = client.post(
        "/login",
        data={"email": "user@example.com", "password": "short", "action": "register"},
    )
    assert short_pw.status_code == 400
