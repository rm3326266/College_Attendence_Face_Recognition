"""Flask endpoint tests. All camera/face model calls are mocked."""
import pytest


@pytest.mark.parametrize("method,path", [
    ("get", "/api/me"),
    ("get", "/api/mode"),
    ("get", "/api/attendance"),
    ("get", "/api/students"),
    ("get", "/api/stats"),
    ("get", "/api/time-status"),
    ("post", "/api/register"),
    ("post", "/api/scan"),
    ("post", "/api/mode"),
    ("post", "/api/force-scan"),
])
def test_unauthenticated_api_is_denied(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401
    assert response.json["error"] == "Authentication required"


@pytest.mark.parametrize("path", ["/", "/maintenance", "/working", "/attendance"])
def test_private_pages_redirect_anonymous_visitors(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_admin_can_use_management_endpoints(client, create_account, sign_in):
    create_account()
    sign_in()
    assert client.get("/").status_code == 200
    assert client.get("/maintenance").status_code == 200
    assert client.get("/working").status_code == 200
    assert client.get("/attendance").status_code == 200
    assert client.get("/api/students").status_code == 200
    assert client.get("/api/stats").status_code == 200


def test_teacher_can_scan_but_not_manage_students(client, create_account, sign_in):
    create_account(role="teacher")
    sign_in("test_teacher")
    assert client.get("/").status_code == 302
    assert client.get("/working").status_code == 200
    assert client.get("/maintenance").status_code == 403
    assert client.get("/api/stats").status_code == 200
    assert client.get("/api/students").status_code == 403
    assert client.get("/api/attendance").status_code == 403
    assert client.post("/api/register", json={}).status_code == 403
    assert client.post("/api/mode", json={"mode": "working"}).status_code == 403
    # Authorized scanning should reach the input-validation stage.
    assert client.post("/api/scan", json={}).status_code == 400


def test_student_access_restricted_to_personal_records(client, db, student_factory, create_account, sign_in):
    me = student_factory("S001", "Own Record")
    other = student_factory("S002", "Another Student")
    db.mark_attendance(me["id"], "SLOT A")
    db.mark_attendance(other["id"], "SLOT B")
    create_account(role="student", student_id=me["id"])
    sign_in("test_student")
    assert client.get("/").status_code == 302
    assert client.get("/attendance").status_code == 200
    assert client.get("/maintenance").status_code == 403
    assert client.get("/working").status_code == 403
    assert client.get("/api/students").status_code == 403
    assert client.get("/api/stats").status_code == 403
    # Even malicious query parameters cannot request someone else's records.
    response = client.get("/api/attendance?roll_no=S002")
    assert response.status_code == 200
    assert response.json["count"] == 1
    assert response.json["records"][0]["roll_no"] == "S001"
    assert client.post("/api/scan", json={}).status_code == 403


def test_admin_can_filter_attendance_by_student(client, db, student_factory, create_account, sign_in):
    student_factory("S001")
    other = student_factory("S002")
    db.mark_attendance(other["id"], "SLOT A")
    create_account()
    sign_in()
    data = client.get("/api/attendance?roll_no=S002").json
    assert data["count"] == 1
    assert data["records"][0]["roll_no"] == "S002"
    assert client.get("/api/attendance?roll_no=NONEXISTENT").json["count"] == 0


def test_admin_mode_switch_and_validation(client, app_module, create_account, sign_in):
    create_account()
    sign_in()
    assert client.get("/api/mode").json["mode"] == "maintenance"
    assert client.post("/api/mode", json={"mode": "invalid"}).status_code == 400
    response = client.post("/api/mode", json={"mode": "working"})
    assert response.status_code == 200
    assert response.json["mode"] == "working"
    assert app_module.current_mode == "working"


def test_force_scan_toggle_for_admin(client, create_account, sign_in):
    create_account()
    sign_in()
    assert client.post("/api/force-scan", json={"enabled": True}).json["force_scan"] is True
    assert client.get("/api/force-scan").json["force_scan"] is True
    assert client.post("/api/force-scan", json={"enabled": False}).json["force_scan"] is False


def test_registration_rejects_missing_inputs(client, create_account, sign_in):
    create_account()
    sign_in()
    result = client.post("/api/register", json={"roll_no": "S001"})
    assert result.status_code == 400
    assert "required" in result.json["error"]


def test_registration_rejects_duplicate_roll(client, student_factory, create_account, sign_in):
    student_factory("S001")
    create_account()
    sign_in()
    result = client.post("/api/register", json={
        "image": "placeholder", "roll_no": "S001", "name": "Duplicate", "branch": "CSE"
    })
    assert result.status_code == 409


def test_scan_rejects_missing_image(client, create_account, sign_in):
    create_account()
    sign_in()
    assert client.post("/api/scan", json={}).status_code == 400


def test_scan_rejects_bad_image(client, create_account, sign_in):
    create_account()
    sign_in()
    response = client.post("/api/scan", json={"image": "not-a-real-image"})
    assert response.status_code == 400
    assert "decode" in response.json["error"]


def prepare_fake_camera(monkeypatch, app_module, faces):
    """Bypass webcam/ML; test only the actual Flask business logic."""
    monkeypatch.setattr(app_module, "decode_base64_image", lambda data: object())
    monkeypatch.setattr(app_module, "detect_faces", lambda image: faces)
    monkeypatch.setattr(app_module, "draw_face_boxes", lambda image, faces, labels: "fake-annotated-jpeg")
    monkeypatch.setattr(app_module, "encode_face", lambda image, face: object())


def test_scan_no_face(client, app_module, create_account, sign_in, monkeypatch):
    create_account()
    sign_in()
    prepare_fake_camera(monkeypatch, app_module, [])
    result = client.post("/api/scan", json={"image": "fake"})
    assert result.status_code == 200
    assert result.json["status"] == "no_face"


def test_scan_multiple_faces(client, app_module, create_account, sign_in, monkeypatch):
    create_account()
    sign_in()
    prepare_fake_camera(monkeypatch, app_module, [object(), object()])
    result = client.post("/api/scan", json={"image": "fake"})
    assert result.status_code == 200
    assert result.json["status"] == "multiple_faces"
    assert result.json["faces_detected"] == 2


def test_scan_encoding_error(client, app_module, create_account, sign_in, monkeypatch):
    create_account()
    sign_in()
    prepare_fake_camera(monkeypatch, app_module, [object()])
    monkeypatch.setattr(app_module, "encode_face", lambda image, face: None)
    result = client.post("/api/scan", json={"image": "fake"})
    assert result.status_code == 500
    assert result.json["status"] == "error"


def test_working_scan_marks_once_and_then_reports_duplicate(
    client, app_module, db, student_factory, create_account, sign_in, monkeypatch
):
    student_factory("S001", "Sample Student")
    create_account()
    sign_in()
    prepare_fake_camera(monkeypatch, app_module, [object()])
    monkeypatch.setattr(app_module, "current_mode", "working")
    monkeypatch.setattr(app_module, "force_scan", True)
    monkeypatch.setattr(app_module, "is_within_time_window", lambda: (False, None))
    monkeypatch.setattr(app_module, "match_face", lambda encoding: ("S001", 0.91))
    first = client.post("/api/scan", json={"image": "fake"})
    assert first.status_code == 200
    assert first.json["status"] == "marked"
    assert first.json["time_slot"] == "FORCE SCAN"
    second = client.post("/api/scan", json={"image": "fake"})
    assert second.json["status"] == "already_marked"
    assert len(db.get_today_attendance("FORCE SCAN")) == 1


def test_working_scan_rejects_outside_window(
    client, app_module, create_account, sign_in, monkeypatch
):
    create_account()
    sign_in()
    prepare_fake_camera(monkeypatch, app_module, [object()])
    monkeypatch.setattr(app_module, "current_mode", "working")
    monkeypatch.setattr(app_module, "force_scan", False)
    monkeypatch.setattr(app_module, "is_within_time_window", lambda: (False, None))
    result = client.post("/api/scan", json={"image": "fake"})
    assert result.json["status"] == "outside_window"


def test_working_scan_unrecognized_face(
    client, app_module, create_account, sign_in, monkeypatch
):
    create_account()
    sign_in()
    prepare_fake_camera(monkeypatch, app_module, [object()])
    monkeypatch.setattr(app_module, "current_mode", "working")
    monkeypatch.setattr(app_module, "force_scan", True)
    monkeypatch.setattr(app_module, "is_within_time_window", lambda: (False, None))
    monkeypatch.setattr(app_module, "match_face", lambda encoding: (None, None))
    result = client.post("/api/scan", json={"image": "fake"})
    assert result.json["status"] == "no_match"
