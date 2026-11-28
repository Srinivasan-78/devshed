"""Flask application factory. Replaces the FastAPI app that lived in
``app/main.py``.

The app is server-rendered (Jinja2) — there is no separate frontend. Auth is a
signed session cookie (Flask's built-in ``session``), not a JWT, so there is no
token for a browser to hold and no cross-origin surface: the pages and the JSON
endpoints are one origin, which is why there is no CORS config here.
"""
import os

from flask import Flask, abort, redirect, request, session, url_for

from app import settings


def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=settings.SECRET_KEY,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"},
        JSON_SORT_KEYS=False,
        MAX_CONTENT_LENGTH=256 * 1024,
    )

    @app.before_request
    def _check_same_origin():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("Origin")
            if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
                abort(403, description="cross-origin state-changing request rejected")

    from app import auth, credentials, resources

    app.register_blueprint(auth.bp)
    app.register_blueprint(credentials.bp)
    app.register_blueprint(resources.bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/")
    def index():
        target = "resources.dashboard" if session.get("user_id") else "auth.login"
        return redirect(url_for(target))

    return app
