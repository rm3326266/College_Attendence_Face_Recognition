"""
Database module for the Automatic Attendance System.
Handles SQLite setup, student CRUD, and attendance operations.
"""

import sqlite3
from datetime import datetime, date
from config import DATABASE_PATH


def get_connection():
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            branch TEXT NOT NULL,
            section TEXT DEFAULT '',
            semester INTEGER DEFAULT 1,
            face_image_path TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date DATE NOT NULL,
            marked_at TIME NOT NULL,
            time_slot TEXT NOT NULL,
            status TEXT DEFAULT 'PRESENT',
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(student_id, date, time_slot)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'teacher', 'student')),
            student_id INTEGER UNIQUE,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)

    conn.commit()
    conn.close()


# ─── Student CRUD ─────────────────────────────────────────────

def add_student(roll_no, name, branch, section="", semester=1, face_image_path=None):
    """Add a new student to the database. Returns the student dict or None if duplicate."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO students (roll_no, name, branch, section, semester, face_image_path)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (roll_no, name, branch, section, semester, face_image_path)
        )
        conn.commit()
        return get_student_by_roll(roll_no)
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_student_by_roll(roll_no):
    """Get a student by roll number. Returns dict or None."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM students WHERE roll_no = ?", (roll_no,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_student_by_id(student_id):
    """Get a student by ID. Returns dict or None."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_students():
    """Get all registered students."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM students ORDER BY roll_no").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_student_count():
    """Get total number of registered students."""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    conn.close()
    return count


# ─── Attendance Operations ────────────────────────────────────

def mark_attendance(student_id, time_slot):
    """
    Mark a student present for today in the given time slot.
    Returns True if newly marked, False if already marked.
    """
    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M:%S")
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO attendance (student_id, date, marked_at, time_slot, status)
               VALUES (?, ?, ?, ?, 'PRESENT')""",
            (student_id, today, now, time_slot)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Already marked for this slot today
        return False
    finally:
        conn.close()


def is_already_marked(student_id, time_slot):
    """Check if a student is already marked for today in the given time slot."""
    today = date.today().isoformat()
    conn = get_connection()
    row = conn.execute(
        """SELECT id FROM attendance
           WHERE student_id = ? AND date = ? AND time_slot = ?""",
        (student_id, today, time_slot)
    ).fetchone()
    conn.close()
    return row is not None


def get_today_attendance(time_slot=None):
    """
    Get today's attendance records, optionally filtered by time slot.
    Returns list of dicts with student details.
    """
    today = date.today().isoformat()
    conn = get_connection()

    if time_slot:
        rows = conn.execute(
            """SELECT a.*, s.roll_no, s.name, s.branch, s.section, s.semester
               FROM attendance a
               JOIN students s ON a.student_id = s.id
               WHERE a.date = ? AND a.time_slot = ?
               ORDER BY a.marked_at""",
            (today, time_slot)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT a.*, s.roll_no, s.name, s.branch, s.section, s.semester
               FROM attendance a
               JOIN students s ON a.student_id = s.id
               WHERE a.date = ?
               ORDER BY a.time_slot, a.marked_at""",
            (today,)
        ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def get_attendance_by_date(target_date):
    """Get attendance records for a specific date."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT a.*, s.roll_no, s.name, s.branch, s.section, s.semester
           FROM attendance a
           JOIN students s ON a.student_id = s.id
           WHERE a.date = ?
           ORDER BY a.time_slot, a.marked_at""",
        (target_date,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_student_attendance(roll_no):
    """Get all attendance records for a specific student."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT a.*, s.roll_no, s.name, s.branch, s.section, s.semester
           FROM attendance a
           JOIN students s ON a.student_id = s.id
           WHERE s.roll_no = ?
           ORDER BY a.date DESC, a.time_slot""",
        (roll_no,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_today_stats():
    """Get summary stats for today's attendance."""
    today = date.today().isoformat()
    conn = get_connection()

    total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]

    # Unique students present today (across all slots)
    present_today = conn.execute(
        """SELECT COUNT(DISTINCT student_id) FROM attendance WHERE date = ?""",
        (today,)
    ).fetchone()[0]

    # Per-slot counts
    slot_stats = conn.execute(
        """SELECT time_slot, COUNT(*) as count
           FROM attendance WHERE date = ?
           GROUP BY time_slot
           ORDER BY time_slot""",
        (today,)
    ).fetchall()

    conn.close()
    return {
        "total_students": total_students,
        "present_today": present_today,
        "absent_today": total_students - present_today,
        "slot_stats": [dict(row) for row in slot_stats]
    }


# Initialize the database on import
init_db()
