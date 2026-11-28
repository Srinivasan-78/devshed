"""Store and list cloud credentials.

The payload is Fernet-encrypted before it touches the database; the plaintext is
only ever re-derived by the Ansible playbooks at provision/destroy time. Listing
returns the provider names only, never the blob. Replaces
``routers/credentials.py``.
"""
import json

from flask import Blueprint, flash, redirect, request, url_for

from app import db
from app.crypto import encrypt
from app.deps import login_required
from app.free_tier import IMPLEMENTED_PROVIDERS, normalize_provider

bp = Blueprint("credentials", __name__)

REQUIRED_CREDENTIAL_KEYS = {
    "aws": {"aws_access_key_id", "aws_secret_access_key"},
    "gcp": {"project_id", "gcp_service_account_json"},
}


@bp.post("/credentials")
@login_required
def store(user):
    raw_provider = request.form.get("provider") or ""
    provider = normalize_provider(raw_provider)
    if provider not in IMPLEMENTED_PROVIDERS:
        flash(f"provider '{raw_provider}' is not implemented for provisioning", "error")
        return redirect(url_for("resources.dashboard"))

    try:
        payload = json.loads(request.form.get("payload") or "")
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        flash("credential payload must be a JSON object", "error")
        return redirect(url_for("resources.dashboard"))

    missing = [k for k in sorted(REQUIRED_CREDENTIAL_KEYS.get(provider, set())) if not str(payload.get(k) or "").strip()]
    if missing:
        flash(f"missing required credential keys for {provider}: {', '.join(missing)}", "error")
        return redirect(url_for("resources.dashboard"))

    db.execute(
        """
        INSERT INTO cloud_credentials (user_id, provider, encrypted_payload)
        VALUES (%(uid)s, %(provider)s, %(enc)s)
        ON CONFLICT (user_id, provider)
        DO UPDATE SET encrypted_payload = EXCLUDED.encrypted_payload
        """,
        {"uid": user["id"], "provider": provider, "enc": encrypt(json.dumps(payload))},
    )
    flash(f"stored credentials for {provider}", "ok")
    return redirect(url_for("resources.dashboard"))


@bp.get("/credentials")
@login_required
def list_configured(user):
    rows = db.query_all(
        "SELECT provider, created_at FROM cloud_credentials "
        "WHERE user_id = %(uid)s ORDER BY provider",
        {"uid": user["id"]},
    )
    return {
        "credentials": [
            {"provider": r["provider"], "created_at": r["created_at"].isoformat()}
            for r in rows
        ]
    }
