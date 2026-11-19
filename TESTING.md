# AutoAttend automated testing

This project uses **pytest** to check core behavior and regressions. Tests run against a **temporary SQLite database** and replace the camera/face model with small fakes where necessary. They do **not** need an administrator token, a real camera, student photographs, or downloaded ONNX weights.

## Set up (PowerShell / Windows)

From the extracted AutoAttend project directory, run:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -v
```

To measure the fraction of source statements executed by the test suite:

```powershell
python -m pytest --cov=app --cov=auth --cov=database --cov=scheduler --cov=camera --cov=face_encoder --cov-report=term-missing
```

Interpret coverage together with the quality of the assertions and test cases; coverage alone does not prove correctness.

## Test map

| File | Focus |
| --- | --- |
| `tests/test_scheduler.py` | Attendance time windows, boundaries, countdowns |
| `tests/test_database.py` | Student persistence, duplicate prevention, foreign keys, attendance records and stats |
| `tests/test_auth.py` | One-time admin setup, passwords, login/logout, account rules and revoked access |
| `tests/test_api.py` | Role permissions, data privacy, input handling, and mocked scan workflows |
| `tests/test_extended_workflows.py` | Maintenance scan branches, registration outcomes, attendance filters, time status and administrator CLI workflows |
| `tests/test_camera.py` | Image decoding, invalid input and annotation |
| `tests/test_face_encoder.py` | Matching logic and encoding failure without a model download |

**Isolation:** `tests/conftest.py` redirects database and encoding file paths into pytest's temporary directory before loading the application. Individual tests get fresh tables and clean Flask client sessions. No test should access your normal `attendance.db`.

## Important limitations

- These tests verify deterministic logic and API behavior; they do **not** measure face-recognition accuracy on real people or validate camera hardware in browsers.
- Teacher class-specific access has not been implemented yet, so tests exercise the **current** teacher permissions.
- CSRF protection, request-size limits and rate limiting are separate planned security improvements. Passing tests is not proof those controls already exist.
- Some tests may reveal bugs. Fix the implementation, not just the assertions, when behavior is genuinely wrong.

## Automated verification (GitHub Actions)

An optional `.github/workflows/tests.yml` workflow runs the test suite on changes pushed to GitHub. It uses no real user data, models or setup tokens.

## Latest coverage improvement round

The user executed the original suite on Windows/Python 3.15: **86 passed, 85% overall statement coverage** (app.py: 74%).

This update adds **20 focused tests** in `tests/test_extended_workflows.py` to exercise important `app.py` branches that were missing in that report. Existing application `.py` modules remain unchanged. The 39 non-Flask tests were re-run successfully here. The additional Flask tests **could not be executed in the authoring environment** because Flask was unavailable; run the commands above locally and inspect their results before claiming a new coverage figure.

Do not aim for 100% coverage at the expense of useful behavior checks. The `if __name__ == '__main__'` development-server startup block is normally outside the Flask test-client execution path; manual/deployment smoke checks are more appropriate for that path.
