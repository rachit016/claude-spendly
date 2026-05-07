# Spec: Backend Routes for Profile Page

## Overview
This feature replaces the hardcoded mock data in the `/profile` route with real database queries. The UI and template built in Step 4 remain unchanged — only `app.py` is updated so the profile page shows the actual logged-in user's name, email, member-since date, real expense totals, recent transactions, and a live category breakdown. This step completes the profile page and makes it genuinely data-driven for the first time.

## Depends on
- Step 1: Database setup (`users` and `expenses` tables must exist)
- Step 2: Registration (real users must be in the DB)
- Step 3: Login/Logout (`session["user_id"]` must be set on login)
- Step 4: Profile page design (`templates/profile.html` must exist)

## Routes
- `GET /profile` — fetch real user + expense data from DB, render `profile.html` — logged-in only

No new routes are added. Only the existing `/profile` view function is updated.

## Database changes
No database changes. The existing `users` and `expenses` tables are sufficient.

## Templates
- **Modify:** `templates/profile.html` — verify the template correctly handles dynamic data (e.g. `member_since` formatting, empty expense list edge case). No structural changes should be required if Step 4 was implemented correctly.

## Files to change
- `app.py` — replace the hardcoded dicts in the `profile()` view with real SQLite queries:
  1. Fetch user row from `users` by `session["user_id"]`
  2. Query all expenses for that user to compute `total_spent` and `transaction_count`
  3. Determine `top_category` by grouping expenses by category and picking the highest sum
  4. Fetch the 5 most recent expenses for the transaction history table
  5. Compute per-category totals and percentages for the category breakdown section

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()` only
- Parameterised queries only — never format user-supplied values into SQL strings
- Passwords hashed with werkzeug (no changes to auth in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- If `session["user_id"]` is not set, redirect to `/login` (guard already exists — keep it)
- Format `member_since` from the `created_at` DB field (e.g. `"January 2024"`) in Python before passing to the template — do not format in Jinja
- Format amounts as `"₹X,XXX.XX"` strings in Python before passing to the template
- Compute category `percent` relative to `total_spent`; guard against division by zero (total_spent = 0)
- Close the DB connection in a `finally` block or call `close_db()` — never leave connections open

## Definition of done
- [ ] Visiting `/profile` without being logged in redirects to `/login`
- [ ] After login, `/profile` shows the actual logged-in user's name and email (not "Alex Rivera")
- [ ] `member_since` reflects the real `created_at` timestamp from the `users` table
- [ ] `total_spent` is the real sum of all expenses for that user
- [ ] `transaction_count` is the real count of expenses for that user
- [ ] `top_category` is the category with the highest total spend for that user
- [ ] The transaction history table shows the 5 most recent real expenses (or fewer if the user has fewer)
- [ ] The category breakdown section shows real per-category totals and correct percentages
- [ ] A newly registered user with no expenses sees `₹0.00` total and an empty transaction list without errors
- [ ] No hardcoded placeholder values remain in the `profile()` view function
