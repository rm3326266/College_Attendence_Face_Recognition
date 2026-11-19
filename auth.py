"""Account persistence and session authorization for AutoAttend."""
import re
import os
import hmac
import sqlite3
from functools import wraps

from flask import abort, g, jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_connection

ROLES = {"admin", "teacher", "student"}


def create_user(username, password, role, student_id=None):
    username = username.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,50}", username):
        raise ValueError("Username must be 3-50 letters, numbers, dots, underscores or hyphens")
    if role not in ROLES:
        raise ValueError("Invalid role")
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")
    if (role == "student") != (student_id is not None):
        raise ValueError("Student accounts must link to a student; other roles must not")
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, role, student_id) VALUES (?, ?, ?, ?)",
            (username, generate_password_hash(password), role, student_id),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_user(user_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, role, student_id, active FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def authenticate(username, password):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
        if row and row["active"] and check_password_hash(row["password_hash"], password):
            return dict(row)
        return None
    finally:
        conn.close()


def load_current_user():
    user_id = session.get("user_id")
    g.user = get_user(user_id) if isinstance(user_id, int) else None
    if g.user and not g.user["active"]:
        g.user = None
    if not g.user:
        session.clear()


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if g.user is None:
                if request.path.startswith("/api/"):
                    return jsonify(error="Authentication required"), 401
                return redirect(url_for("login", next=request.path))
            if g.user["role"] not in roles:
                if request.path.startswith("/api/"):
                    return jsonify(error="Insufficient permissions"), 403
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def accounts_exist():
    conn = get_connection()
    try:
        return conn.execute("SELECT EXISTS(SELECT 1 FROM users)").fetchone()[0] == 1
    finally:
        conn.close()


def create_first_admin(username, password, setup_token):
    """One-time admin bootstrap. Atomic check prevents concurrent setup races."""
    expected = os.environ.get("ADMIN_SETUP_TOKEN", "")
    if not expected or len(expected) < 24:
        raise ValueError("Set ADMIN_SETUP_TOKEN (24+ random characters) in the environment before setup")
    if not hmac.compare_digest(setup_token, expected):
        raise ValueError("Invalid setup token")
    username = username.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,50}", username):
        raise ValueError("Username must be 3-50 letters, numbers, dots, underscores or hyphens")
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT EXISTS(SELECT 1 FROM users)").fetchone()[0]:
            raise ValueError("Initial setup is already complete")
        conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
                     (username, generate_password_hash(password)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
