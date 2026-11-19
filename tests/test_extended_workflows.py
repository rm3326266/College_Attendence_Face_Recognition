"""Additional branch tests for AutoAttend's existing Flask workflows.

Run with pytest; no webcam, face-recognition model, or real student records needed.
All facial processing is mocked and every database fixture uses temporary SQLite.
"""

from datetime import date

import pytest


PASSWORD = "TestPassword#123"


def fake_single_face(monkeypatch, application):
    """Return a single fake face without decoding or persisting an image."""
    monkeypatch.setattr(application, "decode_base64_image", lambda _: object())
    monkeypatch.setattr(application, "detect_faces", lambda _: [object()])
    monkeypatch.setattr(application, "encode_face", lambda *_: object())
    monkeypatch.setattr(application, "draw_face_boxes", lambda *_: "fake-annotated-image")


def registration_payload(**changes):
    data = {
        "image": "fake-image", "roll_no": "aa123", "name": "Demo Student",
        "branch": "cse", "section": "a", "semester": "2",
    }
    data.update(changes)
    return data


def test_authenticated_login_page_redirects_to_dashboard(client, create_account, sign_in):
    create_account()
    assert sign_in().status_code == 302
    response = client.get("/login")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_time_status_includes_force_scan(client, app_module, create_account, sign_in, monkeypatch):
    create_account()
    sign_in()
    monkeypatch.setattr(app_module, "force_scan", True)
    monkeypatch.setattr(app_module, "get_full_time_status", lambda: {"in_window": False, "current_slot": None})
    response = client.get("/api/time-status")
    assert response.status_code == 200
    assert response.json["in_window"] is False
    assert response.json["force_scan"] is True


def test_maintenance_scan_recognizes_existing_student(
    client, app_module, student_factory, create_account, sign_in, monkeypatch
):
    student_factory("S101", "Existing Student")
    create_account()
    sign_in()
    fake_single_face(monkeypatch, app_module)
    monkeypatch.setattr(app_module, "match_face", lambda _: ("S101", 0.92))
    response = client.post("/api/scan", json={"image": "fake"})
    assert response.status_code == 200
    assert response.json["status"] == "existing"
    assert response.json["student"]["roll_no"] == "S101"
    assert response.json["student"]["name"] == "Existing Student"
    assert response.json["confidence"] == 92.0


def test_maintenance_scan_identifies_unregistered_face(
    client, app_module, create_account, sign_in, monkeypatch
):
    create_account()
    sign_in()
    fake_single_face(monkeypatch, app_module)
    monkeypatch.setattr(app_module, "match_face", lambda _: (None, None))
    response = client.post("/api/scan", json={"image": "fake"})
    assert response.status_code == 200
    assert response.json["status"] == "new_face"
    assert response.json["annotated_image"] == "fake-annotated-image"


def test_registration_rejects_undecodable_image(
    client, app_module, create_account, sign_in, monkeypatch
):
    create_account()
    sign_in()
    monkeypatch.setattr(app_module, "decode_base64_image", lambda _: None)
    response = client.post("/api/register", json=registration_payload())
    assert response.status_code == 400
    assert "decode" in response.json["error"]


def test_registration_rejects_image_without_face(
    client, app_module, create_account, sign_in, monkeypatch
):
    create_account()
    sign_in()
    monkeypatch.setattr(app_module, "decode_base64_image", lambda _: object())
    monkeypatch.setattr(app_module, "detect_faces", lambda _: [])
    response = client.post("/api/register", json=registration_payload())
    assert response.status_code == 400
    assert "No face" in response.json["error"]


def test_registration_rejects_failed_encoding(
    client, app_module, create_account, sign_in, monkeypatch
):
    create_account()
    sign_in()
    fake_single_face(monkeypatch, app_module)
    monkeypatch.setattr(app_module, "encode_face", lambda *_: None)
    response = client.post("/api/register", json=registration_payload())
    assert response.status_code == 500
    assert "encode" in response.json["error"]


def test_registration_reports_database_failure(
    client, app_module, create_account, sign_in, monkeypatch
):
    create_account()
    sign_in()
    fake_single_face(monkeypatch, app_module)
    monkeypatch.setattr(app_module, "save_cropped_face", lambda *_: "not-a-real-file.jpg")
    monkeypatch.setattr(app_module, "add_student", lambda *_: None)
    response = client.post("/api/register", json=registration_payload())
    assert response.status_code == 500
    assert "database" in response.json["error"]


def test_registration_creates_student_without_real_face_data(
    client, app_module, db, create_account, sign_in, monkeypatch
):
    create_account()
    sign_in()
    fake_single_face(monkeypatch, app_module)
    monkeypatch.setattr(app_module, "save_cropped_face", lambda *_: "not-a-real-file.jpg")
    saved_encodings = []
    monkeypatch.setattr(app_module, "add_face_encoding", lambda roll, enc: saved_encodings.append(roll))
    response = client.post("/api/register", json=registration_payload())
    assert response.status_code == 200
    assert response.json["status"] == "registered"
    assert response.json["student"]["roll_no"] == "AA123"
    assert response.json["student"]["branch"] == "CSE"
    assert db.get_student_by_roll("AA123")["semester"] == 2
    assert saved_encodings == ["AA123"]


def test_working_scan_in_active_window_records_normal_slot(
    client, app_module, student_factory, create_account, sign_in, monkeypatch
):
    student_factory("S101", "Existing Student")
    create_account()
    sign_in()
    fake_single_face(monkeypatch, app_module)
    monkeypatch.setattr(app_module, "current_mode", "working")
    monkeypatch.setattr(app_module, "force_scan", False)
    monkeypatch.setattr(app_module, "is_within_time_window", lambda: (True, "TEST WINDOW"))
    monkeypatch.setattr(app_module, "match_face", lambda _: ("S101", 0.88))
    response = client.post("/api/scan", json={"image": "fake"})
    assert response.status_code == 200
    assert response.json["status"] == "marked"
    assert response.json["time_slot"] == "TEST WINDOW"
    assert response.json["confidence"] == 88.0


def test_admin_attendance_date_and_slot_filters(
    client, db, student_factory, create_account, sign_in
):
    student = student_factory("S101")
    assert db.mark_attendance(student["id"], "SLOT 1") is True
    assert db.mark_attendance(student["id"], "SLOT 2") is True
    create_account()
    sign_in()
    assert client.get("/api/attendance?slot=SLOT%201").json["count"] == 1
    today = date.today().isoformat()
    assert client.get("/api/attendance?date=" + today).json["count"] == 2
    assert client.get("/api/attendance?date=1999-01-01").json["count"] == 0
    assert client.get("/api/attendance").json["count"] == 2


def test_student_date_slot_filters_stay_within_own_records(
    client, db, student_factory, create_account, sign_in
):
    own = student_factory("S101")
    other = student_factory("S202")
    db.mark_attendance(own["id"], "SLOT 1")
    db.mark_attendance(own["id"], "SLOT 2")
    db.mark_attendance(other["id"], "SLOT 1")
    create_account(role="student", student_id=own["id"])
    sign_in("test_student")
    today = date.today().isoformat()
    response = client.get("/api/attendance", query_string={
        "date": today, "slot": "SLOT 1", "roll_no": "S202"
    })
    assert response.status_code == 200
    assert response.json["count"] == 1
    assert response.json["records"][0]["roll_no"] == "S101"
    assert client.get("/api/attendance?date=1999-01-01").json["count"] == 0
    assert client.get("/api/attendance?slot=NONEXISTENT").json["count"] == 0


def test_missing_linked_student_returns_404(
    client, app_module, student_factory, create_account, sign_in, monkeypatch
):
    student = student_factory("S101")
    create_account(role="student", student_id=student["id"])
    sign_in("test_student")
    monkeypatch.setattr(app_module, "get_student_by_id", lambda _: None)
    response = client.get("/api/attendance")
    assert response.status_code == 404
    assert response.json["error"] == "Student record unavailable"


def test_response_security_headers_present(client):
    response = client.get("/login")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "camera=(self)" in response.headers["Permissions-Policy"]


def test_teacher_cannot_force_scan(
    client, create_account, sign_in
):
    create_account(role="teacher")
    sign_in("test_teacher")
    assert client.post("/api/force-scan", json={"enabled": True}).status_code == 403


def test_cli_teacher_account_creation(
    client, app_module, auth_module, monkeypatch
):
    answers = iter((PASSWORD, PASSWORD))
    monkeypatch.setattr("getpass.getpass", lambda *_: next(answers))
    response = app_module.app.test_cli_runner().invoke(args=[
        "create-user", "--username", "teacher02", "--role", "teacher"
    ])
    assert response.exit_code == 0, response.output
    assert "Account created" in response.output
    assert auth_module.authenticate("teacher02", PASSWORD)["role"] == "teacher"


def test_cli_student_requires_existing_roll(
    client, app_module
):
    response = app_module.app.test_cli_runner().invoke(args=[
        "create-user", "--username", "student02", "--role", "student",
        "--student-roll", "NOTREGISTERED"
    ])
    assert response.exit_code != 0
    assert "Student roll number not found" in response.output


def test_cli_rejects_password_confirmation_mismatch(
    client, app_module, monkeypatch
):
    answers = iter((PASSWORD, "NotTheSamePassword#123"))
    monkeypatch.setattr("getpass.getpass", lambda *_: next(answers))
    response = app_module.app.test_cli_runner().invoke(args=[
        "create-user", "--username", "teacher03", "--role", "teacher"
    ])
    assert response.exit_code != 0
    assert "Passwords do not match" in response.output


def test_cli_student_account_links_to_registered_student(
    client, app_module, auth_module, student_factory, monkeypatch
):
    student = student_factory("S101")
    answers = iter((PASSWORD, PASSWORD))
    monkeypatch.setattr("getpass.getpass", lambda *_: next(answers))
    response = app_module.app.test_cli_runner().invoke(args=[
        "create-user", "--username", "student02", "--role", "student",
        "--student-roll", "s101"
    ])
    assert response.exit_code == 0, response.output
    user = auth_module.authenticate("student02", PASSWORD)
    assert user["student_id"] == student["id"]


def test_cli_duplicate_username_is_rejected(
    client, app_module, auth_module, monkeypatch
):
    auth_module.create_user("teacher02", PASSWORD, "teacher")
    answers = iter((PASSWORD, PASSWORD))
    monkeypatch.setattr("getpass.getpass", lambda *_: next(answers))
    response = app_module.app.test_cli_runner().invoke(args=[
        "create-user", "--username", "teacher02", "--role", "teacher"
    ])
    assert response.exit_code != 0
    assert "Error" in response.output
