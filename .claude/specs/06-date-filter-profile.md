# Spec: Date Filter for Profile Page

## Overview
This feature adds a date range filter to the `/profile` page so users can narrow the summary stats, transaction history, and category breakdown to a specific time window. The route accepts optional `from` and `to` query parameters (ISO dates: `YYYY-MM-DD`). A filter bar rendered above the stats lets users pick a preset period (This Month, Last 3 Months, All Time) or submit a custom date range. When no filter is supplied the page defaults to All Time, preserving existing behaviour.

## Depends on
- Step 1: Database setup (`expenses` table must exist with a `date` TEXT column)
- Step 2: Registration (real users in DB)
- Step 3: Login/Logout (`session["user_id"]` must be set)
- Step 4: Profile page design (`templates/profile.html` must exist)
- Step 5: Backend routes for profile page (real DB queries must be in place)

## Routes
- `GET /profile?from=YYYY-MM-DD&to=YYYY-MM-DD` — same route as Step 5, now reads optional `from`/`to` query params and passes filtered data to the template — logged-in only

No new routes.

## Database changes
No database changes. The existing `expenses.date` TEXT column (`YYYY-MM-DD` format) is used directly in SQL `WHERE date BETWEEN ? AND ?` clauses.

## Templates
- **Modify:** `templates/profile.html` — add a filter bar above the stats section containing:
  - Three preset buttons: **This Month**, **Last 3 Months**, **All Time** (each is an anchor tag linking to `/profile` with the appropriate `from`/`to` params)
  - A small inline form with two `<input type="date">` fields (`from_date`, `to_date`) and an **Apply** button that submits as GET to `/profile`
  - Highlight the active preset when the current query params match it
  - Display the active filter label (e.g. "Showing: April 2026") in a subtitle below the page heading

## Files to change
- `app.py`:
  1. In the `profile()` view, read `request.args.get("from")` and `request.args.get("to")`
  2. Validate both values are valid ISO dates; silently ignore malformed input and fall back to `None`
  3. Pass `date_from` and `date_to` into each of the four helper functions
  4. Pass the resolved `date_from`, `date_to`, and an `active_period` label string to `render_template`
  5. Update `_get_summary_stats`, `_get_transaction_history`, `_get_category_breakdown` to accept optional `date_from` and `date_to` parameters and add `WHERE date BETWEEN ? AND ?` (or just `WHERE user_id = ?`) accordingly
  6. `_get_transaction_history`: when a date filter is active, remove the `LIMIT 5` cap so all matching rows in the window are shown

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()` only
- Parameterised queries only — never format date values into SQL strings
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Date validation must use `datetime.strptime(value, "%Y-%m-%d")` inside a try/except; on failure set the param to `None`
- When `date_from` is `None` and `date_to` is `None`, queries run without a date filter (all-time behaviour)
- When only one bound is provided, treat the missing bound as open-ended (no lower or upper limit)
- The filter bar must be accessible: preset buttons are `<a>` elements, the form uses `<label>` elements for the date inputs
- Preset date ranges must be computed in Python (in the `profile()` view) using `datetime.today()` — do not compute them in the template

## Definition of done
- [ ] Visiting `/profile` with no query params shows all-time data (unchanged from Step 5)
- [ ] Clicking **This Month** filters all stats and transactions to the current calendar month
- [ ] Clicking **Last 3 Months** filters to the past 90 days from today
- [ ] Clicking **All Time** removes any active filter
- [ ] Submitting a custom date range via the form filters data to that range
- [ ] The active preset button is visually highlighted (e.g. `class="active"`)
- [ ] The subtitle below the heading reflects the current filter (e.g. "Showing: May 2026" or "Showing: All Time")
- [ ] A date range with no matching expenses shows `₹0.00` total, zero transactions, and no category rows — without errors
- [ ] Malformed `from`/`to` query params (e.g. `?from=bad`) are silently ignored and fall back to all-time
- [ ] All DB queries remain parameterised — no string formatting of dates into SQL
