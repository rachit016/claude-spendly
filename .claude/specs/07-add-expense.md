# Spec: Add Expense

## Overview
This feature lets a logged-in user add a new expense through a form at `/expenses/add`. It converts the existing placeholder route into a full GET/POST handler that validates input, inserts a row into the `expenses` table, and redirects to the profile page on success. This is the first write operation users can perform on their own data, making it a critical step in the Spendly roadmap.

## Depends on
- Step 01 — Database setup (`expenses` table must exist)
- Step 03 — Login/logout (session-based auth required)
- Step 05 — Profile page (redirect destination after save)

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in only
- `POST /expenses/add` — validate and insert a new expense row, redirect to `/profile` — logged-in only

## Database changes
No database changes. The `expenses` table already exists with all required columns:
- `id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`

## Templates
- **Create:** `templates/add_expense.html` — form with fields: amount, category, date, description; displays validation errors inline

## Files to change
- `app.py` — replace the `add_expense()` stub with a GET/POST handler

## Files to create
- `templates/add_expense.html` — the expense entry form

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (not relevant here, but applies project-wide)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Redirect to `url_for("login")` if the user is not authenticated
- `amount` must be a positive number — reject zero or negative values
- `category` must be one of the fixed set: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- `date` must be a valid `YYYY-MM-DD` string — use `datetime.strptime` to validate
- `description` is optional (may be empty)
- On validation error, re-render the form with the error message and previously entered values preserved
- On success, redirect to `url_for("profile")`
- `user_id` is taken from `session["user_id"]` — never from form input

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in shows a form with fields: Amount, Category, Date, Description
- [ ] Submitting the form with all valid values inserts a row into `expenses` and redirects to `/profile`
- [ ] The new expense appears in the transaction history on the profile page
- [ ] Submitting with a missing or zero amount shows an inline error and does not insert a row
- [ ] Submitting with an invalid date shows an inline error and does not insert a row
- [ ] Submitting with an invalid category shows an inline error and does not insert a row
- [ ] Previously entered form values are preserved when validation fails
