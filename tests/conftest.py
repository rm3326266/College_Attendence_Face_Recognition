"""Isolated pytest fixtures. No real attendance data, webcam or model download."""
import importlib
import sys
from pathlib import Path

import pytest

# Keep imports reliable when tests are launched from the repository root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def database_module(tmp_path_factory):
    """Redirect all storage paths before importing database or face recognition."""
    import config

    sandbox = tmp_path_factory.mktemp("autoattend_bootstrap")
    config.DATABASE_PATH = str(sandbox / "bootstrap.sqlite3")
    config.ENCODINGS_FILE = str(sandbox / "face_encodings.pkl")
    config.KNOWN_FACES_DIR = str(sandbox)
    return importlib.import_module("database")


@pytest.fixture
def db(database_module, tmp_path, monkeypatch):
    """Each test gets fresh SQLite tables and zero personal information."""
    monkeypatch.setattr(database_module, "DATABASE_PATH", str(tmp_path / "attendance_test.sqlite3"))
    database_module.init_db()
    return database_module


@pytest.fixture
def auth_module(db):
    return importlib.import_module("auth")


@pytest.fixture
def client(db, monkeypatch):
    """Flask test client, using isolated DB and a non-secure cookie only for localhost tests."""
    application_module = importlib.import_module("app")
    application = application_module.app
    monkeypatch.setattr(application_module, "current_mode", "maintenance")
    monkeypatch.setattr(application_module, "force_scan", False)
    application.config.update(
        TESTING=True,
        SECRET_KEY="only-for-pytest-not-a-production-secret",
        SESSION_COOKIE_SECURE=False,
    )
    with application.test_client() as test_client:
        yield test_client


@pytest.fixture
def app_module(client):
    return importlib.import_module("app")


@pytest.fixture
def create_account(auth_module):
    def create(role="admin", username=None, student_id=None):
        if username is None:
            username = f"test_{role}"
        return auth_module.create_user(username, "TestPassword#123", role, student_id)
    return create


@pytest.fixture
def sign_in(client):
    def sign_in(username="test_admin", password="TestPassword#123"):
        return client.post("/login", data={"username": username, "password": password})
    return sign_in


@pytest.fixture
def student_factory(db):
    def create(roll_no="AA001", name="Test Student"):
        return db.add_student(roll_no, name, "CSE", "A", 2)
    return create
