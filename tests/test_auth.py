"""Authentication, first-run bootstrap, accounts and sessions."""
import sqlite3

import pytest


SETUP_TOKEN = "temporary-test-setup-token-of-sufficient-length"
PASSWORD = "TestPassword#123"


def test_initial_login_redirects_to_setup(client):
    response = client.get("/login")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/setup")
    assert client.get("/setup").status_code == 200


def test_setup_requires_configured_secret(client, auth_module, monkeypatch):
    monkeypatch.delenv("ADMIN_SETUP_TOKEN", raising=False)
    response = client.post("/setup", data={
        "username": "firstadmin", "password": PASSWORD,
        "confirm_password": PASSWORD, "setup_token": SETUP_TOKEN,
    })
    assert response.status_code == 200
    assert b"ADMIN_SETUP_TOKEN" in response.data
    assert not auth_module.accounts_exist()


def test_setup_rejects_bad_token(client, auth_module, monkeypatch):
    monkeypatch.setenv("ADMIN_SETUP_TOKEN", SETUP_TOKEN)
    response = client.post("/setup", data={
        "username": "firstadmin", "password": PASSWORD,
        "confirm_password": PASSWORD, "setup_token": "incorrect-token",
    })
    assert response.status_code == 200
    assert b"Invalid setup token" in response.data
    assert not auth_module.accounts_exist()


def test_setup_rejects_mismatched_passwords(client, auth_module, monkeypatch):
    monkeypatch.setenv("ADMIN_SETUP_TOKEN", SETUP_TOKEN)
    response = client.post("/setup", data={
        "username": "firstadmin", "password": PASSWORD,
        "confirm_password": "DifferentPassword123!", "setup_token": SETUP_TOKEN,
    })
    assert response.status_code == 200
    assert b"Passwords do not match" in response.data
    assert not auth_module.accounts_exist()


def test_first_admin_created_only_once(client, auth_module, monkeypatch):
    monkeypatch.setenv("ADMIN_SETUP_TOKEN", SETUP_TOKEN)
    payload = {
        "username": "firstadmin", "password": PASSWORD,
        "confirm_password": PASSWORD, "setup_token": SETUP_TOKEN,
    }
    assert client.post("/setup", data=payload).status_code == 302
    assert auth_module.accounts_exist()
    assert auth_module.authenticate("firstadmin", PASSWORD)["role"] == "admin"
    assert client.get("/setup").status_code == 302
    assert client.post("/setup", data={**payload, "username": "intruder"}).status_code == 302
    assert auth_module.authenticate("intruder", PASSWORD) is None


def test_create_user_stores_a_hash_not_a_plaintext_password(db, auth_module):
    auth_module.create_user("testadmin", PASSWORD, "admin")
    connection = db.get_connection()
    try:
        stored = connection.execute("SELECT password_hash FROM users").fetchone()[0]
    finally:
        connection.close()
    assert stored != PASSWORD
    assert auth_module.authenticate("testadmin", PASSWORD) is not None
    assert auth_module.authenticate("testadmin", "wrong") is None


@pytest.mark.parametrize("username, password, role, student_id", [
    ("x", PASSWORD, "admin", None),
    ("white space", PASSWORD, "admin", None),
    ("valid_user", "short", "admin", None),
    ("valid_user", PASSWORD, "owner", None),
    ("valid_user", PASSWORD, "student", None),
    ("valid_user", PASSWORD, "teacher", 10),
])
def test_invalid_accounts_are_rejected(auth_module, username, password, role, student_id):
    with pytest.raises(ValueError):
        auth_module.create_user(username, password, role, student_id)


def test_student_accounts_must_reference_registered_student(auth_module, student_factory):
    student = student_factory()
    user_id = auth_module.create_user("student01", PASSWORD, "student", student["id"])
    assert auth_module.get_user(user_id)["student_id"] == student["id"]


def test_usernames_are_unique_case_insensitively(auth_module):
    auth_module.create_user("SameName", PASSWORD, "admin")
    with pytest.raises(sqlite3.IntegrityError):
        auth_module.create_user("samename", PASSWORD, "teacher")


def test_login_wrong_password_does_not_create_session(client, create_account):
    create_account()
    response = client.post("/login", data={"username": "test_admin", "password": "wrong"})
    assert response.status_code == 200
    assert b"Invalid username or password" in response.data
    assert client.get("/api/me").status_code == 401


def test_login_and_logout_clear_session(client, create_account, sign_in):
    create_account()
    assert sign_in().status_code == 302
    assert client.get("/api/me").json == {"username": "test_admin", "role": "admin"}
    assert client.post("/logout").status_code == 302
    assert client.get("/api/me").status_code == 401


def test_deactivated_user_loses_access(client, create_account, db, sign_in):
    user_id = create_account()
    assert sign_in().status_code == 302
    connection = db.get_connection()
    try:
        connection.execute("UPDATE users SET active = 0 WHERE id = ?", (user_id,))
        connection.commit()
    finally:
        connection.close()
    assert client.get("/api/me").status_code == 401
    assert sign_in().status_code == 200
    assert client.get("/api/me").status_code == 401
