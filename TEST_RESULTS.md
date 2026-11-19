# Test results and next verification

## Verified by user on Windows (original test suite)

- 86 tests passed in 10.28 seconds, 0 failed.
- 85% statement coverage across app, auth, database, scheduler, camera and face_encoder.
- Source-level gap: app.py 74% statement coverage (68 missing of 261).

## This new ZIP

- Adds 20 tests for previously unexercised application branches in `tests/test_extended_workflows.py`.
- No production module logic changed.
- Re-ran 39 database, scheduler, camera and encoder tests here; all passed.
- **New Flask tests not run here** (Flask is absent in this authoring environment). A new overall coverage value cannot be reported until the user runs pytest.

## Run locally

```powershell
python -m pytest -v
python -m pytest --cov=app --cov=auth --cov=database --cov=scheduler --cov=camera --cov=face_encoder --cov-report=term-missing
```

All test database work uses isolated SQLite fixtures; images and ML model calls are mocked in the Flask tests.
