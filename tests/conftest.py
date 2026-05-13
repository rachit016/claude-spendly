"""
Shared pytest fixtures for the Spendly test suite.

All tests use an in-memory SQLite database isolated per test session.
The DB_PATH in database.db is patched before the app module initialises
its module-level init_db()/seed_db() call so that file is never touched.
"""

import sqlite3
import pytest
from werkzeug.security import generate_password_hash

import database.db as db_module


# ---------------------------------------------------------------------------
# In-memory connection registry
# ---------------------------------------------------------------------------
# We keep a single in-memory connection alive for the duration of each test
# so that every get_db() call within a request shares the same `:memory:`
# database (SQLite in-memory databases are connection-scoped; a second
# connect(":memory:") would be a *different*, empty database).

_test_conn: sqlite3.Connection | None = None


def _get_test_db() -> sqlite3.Connection:
    """Return the shared in-memory connection, creating it if necessary."""
    global _test_conn
    if _test_conn is None:
        _test_conn = sqlite3.connect(":memory:", check_same_thread=False)
        _test_conn.row_factory = sqlite3.Row
        _test_conn.execute("PRAGMA foreign_keys = ON")
    return _test_conn


def _close_test_db(conn: sqlite3.Connection) -> None:
    """No-op close: keep the in-memory connection alive across requests."""
    pass  # Do NOT close; closing destroys the in-memory database


def _init_test_db() -> None:
    """Create schema on the in-memory connection without closing it.

    db.init_db() calls conn.close() directly, which destroys the in-memory
    database. This patched version runs the same executescript but skips the
    close so the schema survives for the duration of the test.
    """
    conn = _get_test_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            amount      REAL    NOT NULL,
            category    TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            description TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        );
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def app():
    """
    Yield a Flask app configured for testing with a fresh in-memory database.

    Strategy:
    - Patch database.db.get_db and database.db.close_db so every DB call in
      app.py hits the shared in-memory connection rather than the file on disk.
    - Re-initialise the schema before each test and drop all rows so tests are
      fully isolated.
    """
    global _test_conn

    # Reset the in-memory database for each test
    if _test_conn is not None:
        _test_conn.close()
    _test_conn = sqlite3.connect(":memory:", check_same_thread=False)
    _test_conn.row_factory = sqlite3.Row
    _test_conn.execute("PRAGMA foreign_keys = ON")

    # Patch database.db so app.py routes use our in-memory connection.
    # init_db and seed_db are also patched: the real init_db calls conn.close()
    # which destroys the in-memory database, and seed_db inserts data we don't
    # want — tests seed their own deterministic rows.
    original_get_db = db_module.get_db
    original_close_db = db_module.close_db
    original_init_db = db_module.init_db
    original_seed_db = db_module.seed_db
    db_module.get_db = _get_test_db
    db_module.close_db = _close_test_db
    db_module.init_db = _init_test_db
    db_module.seed_db = lambda: None

    # Import app *after* patching so the module-level init_db/seed_db
    # also hits the in-memory database
    from app import app as flask_app

    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False,
    })

    with flask_app.app_context():
        _init_test_db()

    yield flask_app

    # Restore original functions after each test
    db_module.get_db = original_get_db
    db_module.close_db = original_close_db
    db_module.init_db = original_init_db
    db_module.seed_db = original_seed_db


@pytest.fixture(scope="function")
def client(app):
    """Return a Flask test client bound to the in-memory-db app."""
    return app.test_client()


# ---------------------------------------------------------------------------
# Helper: seed a user and optionally expenses into the in-memory database
# ---------------------------------------------------------------------------

def seed_user(name="Test User", email="test@example.com", password="password123"):
    """Insert a user and return their id."""
    conn = _get_test_db()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, generate_password_hash(password)),
    )
    conn.commit()
    return cursor.lastrowid


def seed_expense(user_id, amount, category, date, description=""):
    """Insert a single expense row and return its id."""
    conn = _get_test_db()
    cursor = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date, description),
    )
    conn.commit()
    return cursor.lastrowid


def login_user(client, email="test@example.com", password="password123"):
    """POST to /login and return the response (follows redirects)."""
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )
