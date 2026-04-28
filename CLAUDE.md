# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the development server (port 5001)
python app.py

# Run tests
pytest

# Run a single test file
pytest tests/test_foo.py

# Run a single test
pytest tests/test_foo.py::test_function_name
```

## Architecture

This is **Spendly**, a Flask expense-tracker web app built as a step-by-step learning project. The codebase is intentionally incomplete — many features are stubbed with placeholder strings, intended to be implemented incrementally.

**Stack:** Flask + SQLite (via raw `sqlite3`) + Jinja2 templates + vanilla JS. No ORM.

### Key files

- `app.py` — all routes defined in one file. Currently only renders templates; POST handlers and auth logic are not yet implemented.
- `database/db.py` — stub for three functions students must implement: `get_db()`, `init_db()`, `close_db()`, `seed_db()`. SQLite connection should use `row_factory = sqlite3.Row` and enable foreign keys.
- `templates/base.html` — shared layout with navbar and footer. All page templates extend this.
- `static/css/style.css` — single stylesheet using CSS custom properties (design tokens in `:root`).
- `static/js/main.js` — empty; JS is added as features are built.

### Planned step-by-step feature sequence (from route stubs in app.py)

1. Database setup (`database/db.py`)
2. Registration (`POST /register`)
3. Login/logout (`POST /login`, `/logout`)
4. User profile (`/profile`)
5–6. Dashboard / expense listing
7. Add expense (`/expenses/add`)
8. Edit expense (`/expenses/<id>/edit`)
9. Delete expense (`/expenses/<id>/delete`)

### Template conventions

- All templates extend `base.html` using `{% extends "base.html" %}` and fill `{% block content %}`.
- Error messages are passed as `error=` in `render_template()` and displayed via `{% if error %}` blocks.
- URLs use `url_for()` throughout — never hardcoded paths (except in `base.html` footer links which still use `/terms` and `/privacy` directly).

### Testing

`pytest` and `pytest-flask` are installed. No test files exist yet. When adding tests, use pytest-flask's `client` fixture pattern with an in-memory SQLite database.
