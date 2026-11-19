# Phase 1: Authentication

This adds a `users` SQLite table, hashed passwords, login/logout, role guards, and a CLI for account creation. Existing students/attendance tables are preserved. No default admin credentials are created.

## Setup

1. Set `SECRET_KEY` to a strong random secret (required for secure sessions; Render already generates one). Keep `FLASK_DEBUG=False` on Render.
2. Create the first admin locally: `flask --app app create-user --username admin --role admin` and enter a 12+ character password.
3. Start the app: `python app.py`. Open `/login`.
4. To add a teacher: `flask --app app create-user --username teacher1 --role teacher`.
5. To add a student account, register the student's face/details as admin first, then run `flask --app app create-user --username student1 --role student --student-roll YOUR_ROLL`.

**Important:** Accounts are in the SQLite file. Creating an admin on your laptop does not create it on Render. On Render, use a persistent database and a secure one-time admin provisioning method before enabling public access. Do not commit `attendance.db` or passwords.

**Current scope:** Admin has full access. Teacher can access working/scanning, but not class-wide records until teacher-class assignments exist. Student can access only their own attendance API and attendance page; student page UI may need adaptation in Phase 2. This release does not yet implement a web UI for admins to create accounts, login rate limiting, or full CSRF protection. Do not treat it as production-ready.


## First-time browser setup (recommended)

1. Set `ADMIN_SETUP_TOKEN` to a random secret with at least 24 characters in your environment (Render: Environment settings). Do not commit it.
2. Set a strong random `SECRET_KEY` environment variable for Flask sessions.
3. Start the app and open `/login`; it redirects to `/setup` when there are no user accounts.
4. Choose your administrator username and password, and enter the setup token.
5. After success, `/setup` is disabled because a user account exists. Sign in at `/login`.
6. Remove `ADMIN_SETUP_TOKEN` from the environment after setup.

To generate a token locally: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

**Note:** A fresh SQLite database on an ephemeral hosting filesystem may cause setup to reappear after a restart. Use persistent storage for real deployments.
