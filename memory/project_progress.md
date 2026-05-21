---
name: Spendly feature progress
description: Which steps are complete and merged to main
type: project
---

Steps complete and merged to main as of 2026-05-19:

- Step 01: Database setup
- Step 02: Registration
- Step 03: Login and Logout
- Step 04: Profile page design
- Step 05: Backend routes for profile page
- Step 06: Date filter for profile page (app.py helpers, profile.html filter bar, profile.css, 60 pytest tests)

**Why:** Each step follows a spec → implement → test → code-review → PR workflow.
**How to apply:** Next feature starts at Step 07 (dashboard / expense listing) or the add-expense route stub.

Test infrastructure lives in `tests/conftest.py` (in-memory SQLite, patched `init_db`/`seed_db`).
Key fix applied: `login` and `register` routes now use `close_db(conn)` via `finally` instead of direct `conn.close()`.
