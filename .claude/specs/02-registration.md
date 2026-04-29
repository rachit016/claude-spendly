# Spec: Registration

## Overview
Implement user registration so new visitors can create a Spendly account. This step adds the `POST /register` handler that validates form input, checks for duplicate emails, hashes the password, inserts the new user into the database, and starts a session to log them in immediately. It also wires Flask's secret key so sessions work throughout the app for all future steps.

## Depends on
- Step 1 (Database setup) — `users` table and `get_db()` must exist and work.

## Routes
- `GET /register` — render registration form — public (already exists, no change needed)
- `POST /register` — process registration form — public

## Database changes
No database changes. The `users` table created in Step 1 already has all required columns (`id`, `name`, `email`, `password_hash`, `created_at`).

## Templates
- **Modify:** `templates/register.html` — already has the form; no structural changes needed. The `{% if error %}` block already exists and will display server-side errors.

## Files to change
- `app.py` — add `POST` method to `/register` route, add Flask secret key config, add session import, implement registration handler.

## Files to create
No new files.

## New dependencies
No new dependencies. `werkzeug.security` is already installed with Flask.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()`
- Parameterised queries only — never use string formatting in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash`
- Use CSS variables — never hardcode hex values (no template changes needed here)
- All templates extend `base.html` (register.html already does)
- Set `app.secret_key` to a fixed dev string (e.g. `"dev-secret-change-in-prod"`) — do NOT use `os.urandom` since that changes on every restart and kills sessions
- Catch the `sqlite3.IntegrityError` that fires on duplicate email; re-render the form with `error="An account with that email already exists."`
- After successful insert, store `session["user_id"]` and `session["user_name"]`, then redirect to `/` (landing) until the dashboard route exists in Step 5
- Validate all three fields are non-empty before hitting the database
- Enforce minimum password length of 8 characters server-side

## Definition of done
- [ ] Submitting the form with valid unique data creates a user row in `users` (verify with a DB browser or print query)
- [ ] Password is stored as a hash, never plain text
- [ ] Submitting a duplicate email re-renders `/register` with an error message visible on the page
- [ ] Submitting with an empty name, email, or password re-renders with a validation error
- [ ] Submitting with a password shorter than 8 characters re-renders with a validation error
- [ ] After successful registration the browser is redirected (HTTP 302) away from `/register`
- [ ] `session["user_id"]` is set after successful registration (confirm in Flask shell or by adding a debug print)
- [ ] App starts without errors after the changes
