# Spec: Login and Logout

## Overview
Implement login and logout so existing Spendly users can authenticate and end their session. This step adds the `POST /login` handler that validates credentials against the database, starts a Flask session on success, and the `GET /logout` handler that clears the session and redirects to the landing page. It also updates the navbar to show context-aware links (Login/Register when logged out, Logout when logged in).

## Depends on
- Step 1 (Database setup) — `users` table and `get_db()` must exist.
- Step 2 (Registration) — users must be able to exist in the database; `session["user_id"]` convention established.

## Routes
- `GET /login` — render login form — public (already exists as stub, needs template)
- `POST /login` — process login form — public
- `GET /logout` — clear session and redirect to landing — public (currently returns placeholder string)

## Database changes
No database changes. The `users` table already has `email` and `password_hash` columns sufficient for authentication.

## Templates
- **Create:** `templates/login.html` — login form with email and password fields, error block, and link to `/register`
- **Modify:** `templates/base.html` — update navbar links to show "Logout" when `session.user_id` is set, and "Login" / "Register" when not

## Files to change
- `app.py` — add `POST` method to `/login` route, implement login handler; implement `/logout` handler (replace placeholder string)
- `templates/base.html` — conditional navbar links based on session state

## Files to create
- `templates/login.html` — login form template

## New dependencies
No new dependencies. `werkzeug.security.check_password_hash` is already installed with Flask.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()`
- Parameterised queries only — never use string formatting in SQL
- Passwords verified with `werkzeug.security.check_password_hash`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Use a single generic error message ("Invalid email or password.") for both bad email and bad password — never reveal which field was wrong
- After successful login store `session["user_id"]` and `session["user_name"]`, then redirect to `/` (landing) until the dashboard exists in Step 5
- `/logout` must call `session.clear()` and redirect to `url_for("landing")`
- Validate that both email and password fields are non-empty before hitting the database
- `login.html` must use the same `{% if error %}` pattern as `register.html`

## Definition of done
- [ ] `GET /login` renders the login form with email and password inputs
- [ ] Submitting correct credentials sets `session["user_id"]` and redirects away from `/login`
- [ ] Submitting an email that does not exist re-renders `/login` with "Invalid email or password."
- [ ] Submitting a correct email but wrong password re-renders `/login` with "Invalid email or password."
- [ ] Submitting with empty email or password re-renders `/login` with a validation error
- [ ] `GET /logout` clears the session and redirects to the landing page (HTTP 302)
- [ ] After logout, `session["user_id"]` is no longer set
- [ ] Navbar shows "Login" and "Register" when no session exists
- [ ] Navbar shows "Logout" when `session["user_id"]` is set
- [ ] App starts without errors after the changes
