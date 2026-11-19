"""
Flask Application for the Automatic Attendance System.
Provides API endpoints for face scanning and mode management.
"""

from flask import Flask, request, jsonify, render_template, redirect, url_for, session, g, abort
from config import SECRET_KEY, DEBUG, HOST, PORT, SCAN_INTERVAL_MS
from database import (
    add_student, get_student_by_roll, get_student_by_id, get_all_students,
    get_student_count, mark_attendance, is_already_marked,
    get_today_attendance, get_today_stats, get_attendance_by_date,
    get_student_attendance
)
from camera import decode_base64_image, detect_faces, draw_face_boxes
from face_encoder import (
    encode_face, match_face, add_face_encoding,
    save_cropped_face, load_encodings, get_known_count
)
from auth import authenticate, create_user, load_current_user, role_required, accounts_exist, create_first_admin
from scheduler import is_within_time_window, get_current_time_slot, get_all_windows_status, get_full_time_status

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=not DEBUG,
    PERMANENT_SESSION_LIFETIME=__import__("datetime").timedelta(hours=8),
)
app.before_request(load_current_user)


@app.route("/setup", methods=["GET", "POST"])
def first_run_setup():
    """First administrator is created through the browser only once."""
    if accounts_exist():
        return redirect(url_for("login"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        confirmation = request.form.get("confirm_password", "")
        if password != confirmation:
            error = "Passwords do not match"
        else:
            try:
                create_first_admin(username, password, request.form.get("setup_token", ""))
                return redirect(url_for("login"))
            except ValueError as exc:
                error = str(exc)
            except __import__("sqlite3").IntegrityError:
                error = "Account setup could not be completed"
    return render_template("setup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if not accounts_exist():
        return redirect(url_for("first_run_setup"))
    if g.user:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        user = authenticate(request.form.get("username", ""), request.form.get("password", ""))
        if user:
            session.clear()
            session["user_id"] = user["id"]
            session.permanent = True
            return redirect(url_for("index"))
        error = "Invalid username or password"
    return render_template("login.html", error=error)


@app.route("/logout", methods=["POST"])
@role_required("admin", "teacher", "student")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/api/me")
@role_required("admin", "teacher", "student")
def current_user():
    return jsonify({"username": g.user["username"], "role": g.user["role"]})


@app.cli.command("create-user")
@__import__("click").option("--username", prompt=True)
@__import__("click").option("--role", type=__import__("click").Choice(["admin", "teacher", "student"]), prompt=True)
@__import__("click").option("--student-roll", default="", help="Required for student accounts")
def create_user_command(username, role, student_roll):
    """Create an account locally, without exposing a public registration API."""
    import click
    from getpass import getpass
    student_id = None
    if role == "student":
        student = get_student_by_roll(student_roll.strip().upper())
        if not student:
            raise click.ClickException("Student roll number not found; register the student first")
        student_id = student["id"]
    password = getpass("Password (12+ characters): ")
    confirm = getpass("Confirm password: ")
    if password != confirm:
        raise click.ClickException("Passwords do not match")
    try:
        create_user(username, password, role, student_id)
    except (ValueError, __import__("sqlite3").IntegrityError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo("Account created")


# ─── Add headers for camera access ───────────────────────────
@app.after_request
def add_security_headers(response):
    """Add headers to allow camera access and enable features."""
    response.headers["Permissions-Policy"] = "camera=(self), microphone=()"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

# ─── App State ────────────────────────────────────────────────
# Current mode: "maintenance" or "working"
current_mode = "maintenance"
# Force scan: bypass time window checks (for admin/demo)
force_scan = False


# ─── API: Mode Management ────────────────────────────────────

@app.route("/api/mode", methods=["GET"])
@role_required("admin", "teacher")
def get_mode():
    """Get the current operating mode."""
    return jsonify({"mode": current_mode})


@app.route("/api/mode", methods=["POST"])
@role_required("admin")
def set_mode():
    """Switch between maintenance and working mode."""
    global current_mode
    data = request.get_json()
    mode = data.get("mode", "").lower()

    if mode not in ("maintenance", "working"):
        return jsonify({"error": "Invalid mode. Use 'maintenance' or 'working'."}), 400

    current_mode = mode
    return jsonify({"mode": current_mode, "message": f"Switched to {current_mode} mode."})


# ─── API: Force Scan Toggle ──────────────────────────────────

@app.route("/api/force-scan", methods=["GET"])
@role_required("admin", "teacher")
def get_force_scan():
    """Get the current force-scan state."""
    return jsonify({"force_scan": force_scan})


@app.route("/api/force-scan", methods=["POST"])
@role_required("admin")
def toggle_force_scan():
    """Toggle force-scan mode (bypass time window checks)."""
    global force_scan
    data = request.get_json()
    force_scan = bool(data.get("enabled", not force_scan))
    return jsonify({
        "force_scan": force_scan,
        "message": "Force scan ENABLED — time windows bypassed." if force_scan
                   else "Force scan DISABLED — normal schedule active."
    })


# ─── API: Time Status ────────────────────────────────────────

@app.route("/api/time-status", methods=["GET"])
@role_required("admin", "teacher")
def time_status():
    """Get comprehensive time window status with countdowns."""
    status = get_full_time_status()
    status["force_scan"] = force_scan
    return jsonify(status)


# ─── API: Face Scan ──────────────────────────────────────────

@app.route("/api/scan", methods=["POST"])
@role_required("admin", "teacher")
def scan_face():
    """
    Core scanning endpoint. Receives a base64 image from the browser camera.
    Behavior depends on the current mode:

    MAINTENANCE MODE:
        - Detects face → encodes → matches against DB
        - If new face: returns {status: "new_face"} with the face data
        - If existing face: returns {status: "existing", student: {...}}

    WORKING MODE:
        - Checks if within a time window first
        - Detects face → encodes → matches
        - If matched & not already marked: marks present
        - If matched & already marked: returns already_marked
        - If not matched: returns no_match
    """
    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"error": "No image provided."}), 400

    # Decode the base64 image (returns BGR)
    image_bgr = decode_base64_image(data["image"])
    if image_bgr is None:
        return jsonify({"error": "Failed to decode image."}), 400

    # Detect faces using YuNet
    faces = detect_faces(image_bgr)
    if faces is None or len(faces) == 0:
        return jsonify({
            "status": "no_face",
            "message": "No face detected. Please position your face in front of the camera."
        })

    # Only process when exactly ONE face is in the frame
    if len(faces) > 1:
        annotated = draw_face_boxes(image_bgr, faces, [None] * len(faces))
        return jsonify({
            "status": "multiple_faces",
            "message": f"{len(faces)} faces detected. Please ensure only one person is in front of the camera.",
            "faces_detected": len(faces),
            "annotated_image": annotated
        })

    # Single face — proceed
    face = faces[0]

    # Encode the detected face using SFace
    encoding = encode_face(image_bgr, face)
    if encoding is None:
        return jsonify({"status": "error", "message": "Failed to encode face."}), 500

    # ─── MAINTENANCE MODE ─────────────────────────────────
    if current_mode == "maintenance":
        return _handle_maintenance_scan(image_bgr, face, encoding)

    # ─── WORKING MODE ─────────────────────────────────────
    else:
        return _handle_working_scan(image_bgr, face, encoding)


def _handle_maintenance_scan(image_bgr, face, encoding):
    """Handle face scan in maintenance mode."""
    matched_roll, score = match_face(encoding)

    if matched_roll:
        # Face already exists — return student details
        student = get_student_by_roll(matched_roll)
        annotated = draw_face_boxes(image_bgr, [face], [student["name"]])
        return jsonify({
            "status": "existing",
            "message": "Student already registered!",
            "student": {
                "roll_no": student["roll_no"],
                "name": student["name"],
                "branch": student["branch"],
                "section": student["section"],
                "semester": student["semester"],
                "registered_at": student["registered_at"]
            },
            "confidence": round(score * 100, 1),
            "annotated_image": annotated
        })
    else:
        # New face — return face data for registration form
        annotated = draw_face_boxes(image_bgr, [face], ["New Face"])
        return jsonify({
            "status": "new_face",
            "message": "New face detected! Please enter student details.",
            "annotated_image": annotated
        })


def _handle_working_scan(image_bgr, face, encoding):
    """Handle face scan in working mode — single face guaranteed by caller."""
    # Check if we're within a scanning time window (unless force_scan is on)
    in_window, time_slot = is_within_time_window()

    if not in_window and not force_scan:
        return jsonify({
            "status": "outside_window",
            "message": "Not within a scanning time window.",
            "windows": get_all_windows_status()
        })

    # If force scanning outside a window, use a special slot label
    if not in_window and force_scan:
        time_slot = "FORCE SCAN"

    # Try to match the face
    matched_roll, score = match_face(encoding)

    if matched_roll:
        student = get_student_by_roll(matched_roll)
        annotated = draw_face_boxes(image_bgr, [face], [student["name"]])

        # Check if already marked for this slot
        if is_already_marked(student["id"], time_slot):
            return jsonify({
                "status": "already_marked",
                "message": f"{student['name']} is already marked present for {time_slot}.",
                "student": {"name": student["name"], "roll_no": student["roll_no"]},
                "annotated_image": annotated
            })

        # Mark attendance
        mark_attendance(student["id"], time_slot)
        return jsonify({
            "status": "marked",
            "message": f"✅ {student['name']} marked PRESENT for {time_slot}.",
            "student": {"name": student["name"], "roll_no": student["roll_no"]},
            "time_slot": time_slot,
            "confidence": round(score * 100, 1),
            "annotated_image": annotated
        })
    else:
        return jsonify({
            "status": "no_match",
            "message": "Face not recognized. Continuing scan..."
        })


# ─── API: Register Student (from maintenance mode) ───────────

@app.route("/api/register", methods=["POST"])
@role_required("admin")
def register_student():
    """
    Register a new student with their face encoding.
    Called after a new face is detected in maintenance mode and the admin fills the form.
    """
    data = request.get_json()
    required = ["image", "roll_no", "name", "branch"]
    for field in required:
        if field not in data or not data[field].strip():
            return jsonify({"error": f"'{field}' is required."}), 400

    roll_no = data["roll_no"].strip().upper()
    name = data["name"].strip()
    branch = data["branch"].strip().upper()
    section = data.get("section", "").strip().upper()
    semester = int(data.get("semester", 1))

    # Check if roll number already exists
    existing = get_student_by_roll(roll_no)
    if existing:
        return jsonify({
            "error": f"Roll number {roll_no} is already registered to {existing['name']}."
        }), 409

    # Decode image and detect face
    image_bgr = decode_base64_image(data["image"])
    if image_bgr is None:
        return jsonify({"error": "Failed to decode image."}), 400

    faces = detect_faces(image_bgr)
    if faces is None or len(faces) == 0:
        return jsonify({"error": "No face detected in the image."}), 400

    face = faces[0]
    encoding = encode_face(image_bgr, face)
    if encoding is None:
        return jsonify({"error": "Failed to encode face."}), 500

    # Save cropped face image
    face_path = save_cropped_face(roll_no, image_bgr, face)

    # Add to database
    student = add_student(roll_no, name, branch, section, semester, face_path)
    if not student:
        return jsonify({"error": "Failed to save student to database."}), 500

    # Add face encoding to the in-memory cache + pickle
    add_face_encoding(roll_no, encoding)

    return jsonify({
        "status": "registered",
        "message": f"✅ {name} ({roll_no}) registered successfully!",
        "student": {
            "roll_no": student["roll_no"],
            "name": student["name"],
            "branch": student["branch"],
            "section": student["section"],
            "semester": student["semester"]
        }
    })


# ─── API: Dashboard Data ─────────────────────────────────────

@app.route("/api/stats", methods=["GET"])
@role_required("admin", "teacher")
def get_stats():
    """Get today's attendance statistics."""
    stats = get_today_stats()
    stats["mode"] = current_mode
    stats["known_faces"] = get_known_count()
    stats["windows"] = get_all_windows_status()
    stats["force_scan"] = force_scan
    return jsonify(stats)


@app.route("/api/attendance", methods=["GET"])
@role_required("admin", "student")
def get_attendance():
    """Get attendance records. Optional query params: date, slot, roll_no."""
    target_date = request.args.get("date")
    slot = request.args.get("slot")
    roll_no = request.args.get("roll_no")

    if g.user["role"] == "student":
        student = get_student_by_id(g.user["student_id"])
        if not student:
            return jsonify({"error": "Student record unavailable"}), 404
        records = get_student_attendance(student["roll_no"])
        if target_date:
            records = [r for r in records if r["date"] == target_date]
        if slot:
            records = [r for r in records if r["time_slot"] == slot]
    elif roll_no:
        records = get_student_attendance(roll_no)
    elif target_date:
        records = get_attendance_by_date(target_date)
    else:
        records = get_today_attendance(slot)

    return jsonify({"records": records, "count": len(records)})


@app.route("/api/students", methods=["GET"])
@role_required("admin")
def list_students():
    """Get all registered students."""
    students = get_all_students()
    return jsonify({"students": students, "count": len(students)})


# ─── Page Routes ──────────────────────────────────────────────

@app.route("/")
@role_required("admin", "teacher", "student")
def index():
    """Main dashboard page."""
    if g.user["role"] == "student":
        return redirect(url_for("attendance_page"))
    if g.user["role"] == "teacher":
        return redirect(url_for("working_page"))
    return render_template("dashboard.html", mode=current_mode)


@app.route("/maintenance")
@role_required("admin")
def maintenance_page():
    """Maintenance mode page with camera and registration form."""
    return render_template("maintenance.html", mode=current_mode)


@app.route("/working")
@role_required("admin", "teacher")
def working_page():
    """Working mode page with auto-scanning camera."""
    return render_template("working.html", mode=current_mode)


@app.route("/attendance")
@role_required("admin", "student")
def attendance_page():
    """Attendance records page."""
    return render_template("attendance.html", mode=current_mode)


# ─── Run ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    use_ssl = "--ssl" in sys.argv

    print(f"🎓 Automatic Attendance System")
    print(f"   Mode: {current_mode}")
    print(f"   Known faces: {get_known_count()}")
    print(f"   Students in DB: {get_student_count()}")

    if use_ssl:
        # HTTPS with self-signed cert (allows camera on LAN IPs)
        print(f"   🔒 HTTPS enabled (self-signed certificate)")
        print(f"   Running on https://{HOST}:{PORT}")
        print(f"   ⚠️  Browser will show a security warning — click 'Advanced' → 'Proceed'")
        app.run(host=HOST, port=PORT, debug=DEBUG, ssl_context="adhoc")
    else:
        print(f"   Running on http://{HOST}:{PORT}")
        print(f"   💡 Use http://localhost:{PORT} for camera access")
        print(f"   💡 For LAN access with camera, run: python app.py --ssl")
        app.run(host=HOST, port=PORT, debug=DEBUG)
