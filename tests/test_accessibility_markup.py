"""Fast accessibility regressions; not a substitute for browser/AT checks."""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"


def template(name):
    return (TEMPLATES / name).read_text(encoding="utf-8")


def test_all_templates_parse():
    for file in TEMPLATES.glob("*.html"):
        Environment().parse(file.read_text(encoding="utf-8"))


def test_skip_links_in_shared_and_auth_pages():
    for name in ("base.html", "setup.html", "login.html"):
        html = template(name)
        assert 'href="#main-content"' in html
        assert 'id="main-content"' in html


def test_navigation_marks_current_page_and_flash_is_announced():
    html = template("base.html")
    assert 'aria-label="Main navigation"' in html
    assert 'aria-current="page"' in html
    assert 'id="flash-container" role="status"' in html


def test_camera_pages_have_accessible_status_and_announcements():
    for name in ("maintenance.html", "working.html"):
        html = template(name)
        assert 'aria-label="Live camera preview used for face recognition"' in html
        assert 'id="scan-announcement"' in html
        assert 'aria-live="polite"' in html
        assert 'id="camera-status"' in html


def test_registration_form_keeps_explicit_input_labels():
    html = template("maintenance.html")
    for control in ("reg-name", "reg-roll", "reg-branch", "reg-section", "reg-semester"):
        assert f'<label for="{control}">' in html
        assert f'id="{control}"' in html
    assert 'id="register-heading" tabindex="-1"' in html


def test_attendance_tables_have_captions_and_column_scopes():
    html = template("attendance.html")
    assert html.count('<caption class="sr-only">') == 2
    assert html.count('scope="col"') == 16
    assert html.count('tabindex="0"') >= 2


def test_focus_and_reduced_motion_styles_exist():
    css = (ROOT / "static/css/style.css").read_text(encoding="utf-8")
    assert ":focus-visible" in css
    assert "prefers-reduced-motion: reduce" in css
    assert ".skip-link:focus" in css


def test_announcements_skip_repetitive_empty_scans():
    js = (ROOT / "static/js/camera.js").read_text(encoding="utf-8")
    assert '["no_face", "no_match"].includes(result.status)' in js
