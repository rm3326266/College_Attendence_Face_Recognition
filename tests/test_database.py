"""SQLite integration tests use only a temporary database."""
from datetime import date
import sqlite3


def test_empty_database(db):
    assert db.get_student_count() == 0
    assert db.get_all_students() == []
    assert db.get_today_stats()["present_today"] == 0


def test_register_student_and_find_by_roll_or_id(db, student_factory):
    student = student_factory("AA002", "Sample Learner")
    assert student["name"] == "Sample Learner"
    assert student["branch"] == "CSE"
    assert db.get_student_by_roll("AA002")["id"] == student["id"]
    assert db.get_student_by_id(student["id"])["roll_no"] == "AA002"
    assert db.get_student_count() == 1


def test_duplicate_roll_number_returns_none(db, student_factory):
    student_factory("AA002")
    assert db.add_student("AA002", "Other Person", "ECE") is None
    assert db.get_student_count() == 1


def test_unknown_student_is_none(db):
    assert db.get_student_by_roll("MISSING") is None
    assert db.get_student_by_id(9999) is None


def test_students_sorted_by_roll_number(db, student_factory):
    student_factory("ZZ010", "Second")
    student_factory("AA001", "First")
    assert [s["roll_no"] for s in db.get_all_students()] == ["AA001", "ZZ010"]


def test_attendance_only_once_per_day_and_slot(db, student_factory):
    student = student_factory()
    assert db.mark_attendance(student["id"], "10:00 AM - 10:15 AM") is True
    assert db.is_already_marked(student["id"], "10:00 AM - 10:15 AM") is True
    assert db.mark_attendance(student["id"], "10:00 AM - 10:15 AM") is False
    assert len(db.get_today_attendance()) == 1
    assert db.mark_attendance(student["id"], "11:00 AM - 11:15 AM") is True
    assert len(db.get_today_attendance()) == 2


def test_attendance_filters(db, student_factory):
    student = student_factory()
    db.mark_attendance(student["id"], "SLOT A")
    db.mark_attendance(student["id"], "SLOT B")
    assert len(db.get_today_attendance("SLOT A")) == 1
    assert len(db.get_today_attendance("NONEXISTENT")) == 0
    assert len(db.get_attendance_by_date(date.today().isoformat())) == 2
    assert db.get_attendance_by_date("2001-01-01") == []
    assert len(db.get_student_attendance(student["roll_no"])) == 2


def test_statistics_count_distinct_students(db, student_factory):
    one = student_factory("AA001", "One")
    student_factory("AA002", "Two")
    db.mark_attendance(one["id"], "SLOT A")
    db.mark_attendance(one["id"], "SLOT B")
    stats = db.get_today_stats()
    assert stats["total_students"] == 2
    assert stats["present_today"] == 1
    assert stats["absent_today"] == 1
    assert sorted(s["count"] for s in stats["slot_stats"]) == [1, 1]


def test_foreign_key_enforced(db):
    connection = db.get_connection()
    try:
        with __import__("pytest").raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO attendance (student_id, date, marked_at, time_slot) "
                "VALUES (999999, '2026-01-05', '10:00:00', 'TEST')"
            )
    finally:
        connection.close()
