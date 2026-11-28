"""Register / login / logout. Session cookie + bcrypt password hashing.
Replaces ``routers/auth.py``, which issued JWTs.
"""
import re

import bcrypt
import psycopg2
from flask import Blueprint, redirect, render_template, request, session, url_for

from app import db

bp = Blueprint("auth", __name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("resources.dashboard"))
        return render_template("login.html")

    email = (request.form.get("email") or "").strip().lower()
    raw_password = request.form.get("password") or ""
    password = raw_password.encode()
    want_register = request.form.get("action") == "register"

    if not email or not raw_password:
        return render_template("login.html", error="email and password required"), 400
    if not EMAIL_RE.match(email):
        return render_template("login.html", error="invalid email format"), 400

    if want_register:
        if len(raw_password) < 8:
            return render_template("login.html", error="password must be at least 8 characters"), 400
        if db.query_one("SELECT 1 FROM users WHERE email = %(e)s", {"e": email}):
            return render_template("login.html", error="email already registered"), 400
        pw_hash = bcrypt.hashpw(password, bcrypt.gensalt()).decode()
        try:
            row = db.execute_returning(
                "INSERT INTO users (email, hashed_password) VALUES (%(e)s, %(p)s) RETURNING id",
                {"e": email, "p": pw_hash},
            )
        except psycopg2.IntegrityError:
            return render_template("login.html", error="email already registered"), 400
        session.clear()
        session["user_id"] = str(row["id"])
        return redirect(url_for("resources.dashboard"))

    user = db.query_one(
        "SELECT id, hashed_password FROM users WHERE email = %(e)s", {"e": email}
    )
    if not user or not bcrypt.checkpw(password, user["hashed_password"].encode()):
        return render_template("login.html", error="invalid credentials"), 401
    session.clear()
    session["user_id"] = str(user["id"])
    return redirect(url_for("resources.dashboard"))


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
