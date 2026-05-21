"""
Tests for Step 07: Add Expense
==============================

Spec: .claude/specs/07-add-expense.md

The /expenses/add route accepts GET and POST requests from authenticated users.
A GET renders the expense entry form; a POST validates the submitted data and,
on success, inserts a row into the `expenses` table and redirects to /profile.
On validation failure the form is re-rendered with an inline error message and
previously entered values preserved.

Rules under test (sourced from spec "Rules for implementation" and "Definition
of done" sections — NOT from the implementation):

- Unauthenticated GET  /expenses/add  -> redirect to /login
- Unauthenticated POST /expenses/add  -> redirect to /login
- GET while logged in renders a form with amount, category, date, description
- POST with all valid values inserts exactly one row and redirects to /profile
- The newly inserted expense appears in the DB after a successful POST
- Missing amount             -> inline error, zero new rows in DB
- Zero amount                -> inline error, zero new rows in DB
- Negative amount            -> inline error, zero new rows in DB
- Non-numeric amount         -> inline error, zero new rows in DB
- Invalid category           -> inline error, zero new rows in DB
- Invalid / missing date     -> inline error, zero new rows in DB
- On validation failure, previously entered form values are re-rendered
- `user_id` is taken from the session, never from form input
"""

import pytest

from conftest import seed_user, seed_expense, login_user, _get_test_db


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

VALID_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]

VALID_FORM = {
    "amount": "42.50",
    "category": "Food",
    "date": "2026-05-01",
    "description": "Test lunch",
}


def _expense_count(user_id=None):
    """Return the number of expense rows, optionally filtered by user_id."""
    conn = _get_test_db()
    if user_id is not None:
        row = conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()
    return row[0]


def _get_all_expenses(user_id=None):
    """Return all expense rows as sqlite3.Row objects, optionally by user_id."""
    conn = _get_test_db()
    if user_id is not None:
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM expenses ORDER BY id DESC"
    ).fetchall()


# ---------------------------------------------------------------------------
# Auth Guard Tests
# ---------------------------------------------------------------------------

class TestAuthGuard:
    """Unauthenticated requests must be redirected to /login."""

    def test_get_while_logged_out_redirects_to_login(self, client):
        """GET /expenses/add without a session must return a redirect to /login."""
        response = client.get("/expenses/add")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_post_while_logged_out_redirects_to_login(self, client):
        """POST /expenses/add without a session must return a redirect to /login."""
        response = client.post("/expenses/add", data=VALID_FORM)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_get_while_logged_out_does_not_render_form(self, client):
        """Unauthenticated GET must not render the expense form HTML."""
        response = client.get("/expenses/add", follow_redirects=True)
        # After following the redirect we should be on the login page, not the form
        assert b"amount" not in response.data or b"password" in response.data

    def test_post_while_logged_out_inserts_no_rows(self, client):
        """Unauthenticated POST must not insert any expense rows."""
        before = _expense_count()
        client.post("/expenses/add", data=VALID_FORM)
        assert _expense_count() == before


# ---------------------------------------------------------------------------
# GET /expenses/add — Form Rendering
# ---------------------------------------------------------------------------

class TestGetFormRendering:
    """Authenticated GET /expenses/add must render the expense entry form."""

    @pytest.fixture(autouse=True)
    def logged_in(self, client):
        seed_user()
        login_user(client)

    def test_get_returns_200(self, client):
        """GET /expenses/add while logged in must return HTTP 200."""
        response = client.get("/expenses/add")
        assert response.status_code == 200

    def test_get_renders_amount_field(self, client):
        """The form must contain an amount input field."""
        response = client.get("/expenses/add")
        assert b"amount" in response.data

    def test_get_renders_category_field(self, client):
        """The form must contain a category selection field."""
        response = client.get("/expenses/add")
        assert b"category" in response.data

    def test_get_renders_date_field(self, client):
        """The form must contain a date input field."""
        response = client.get("/expenses/add")
        assert b"date" in response.data

    def test_get_renders_description_field(self, client):
        """The form must contain a description input field."""
        response = client.get("/expenses/add")
        assert b"description" in response.data

    def test_get_renders_all_valid_categories_as_options(self, client):
        """All seven valid categories must appear as selectable options in the form."""
        response = client.get("/expenses/add")
        html = response.data.decode()
        for cat in VALID_CATEGORIES:
            assert cat in html, f"Category '{cat}' missing from form"

    def test_get_renders_no_error_on_fresh_load(self, client):
        """A fresh GET must not show any inline error message."""
        response = client.get("/expenses/add")
        # Spec: errors only appear after a failed POST
        assert b"error" not in response.data.lower() or b"class=\"error" not in response.data


# ---------------------------------------------------------------------------
# Happy Path: POST with Valid Data
# ---------------------------------------------------------------------------

class TestAddExpenseHappyPath:
    """Valid form submissions must insert a row and redirect to /profile."""

    @pytest.fixture(autouse=True)
    def logged_in_user(self, client):
        self.user_id = seed_user()
        login_user(client)

    def test_valid_post_redirects_to_profile(self, client):
        """Posting valid data must redirect (302) to /profile."""
        response = client.post("/expenses/add", data=VALID_FORM)
        assert response.status_code == 302
        assert "/profile" in response.headers["Location"]

    def test_valid_post_inserts_exactly_one_row(self, client):
        """Exactly one new expense row must be present after a successful POST."""
        before = _expense_count(self.user_id)
        client.post("/expenses/add", data=VALID_FORM)
        assert _expense_count(self.user_id) == before + 1

    def test_valid_post_stores_correct_amount(self, client):
        """The inserted row must have the submitted amount."""
        client.post("/expenses/add", data=VALID_FORM)
        rows = _get_all_expenses(self.user_id)
        assert len(rows) > 0
        assert float(rows[0]["amount"]) == pytest.approx(42.50)

    def test_valid_post_stores_correct_category(self, client):
        """The inserted row must have the submitted category."""
        client.post("/expenses/add", data=VALID_FORM)
        rows = _get_all_expenses(self.user_id)
        assert rows[0]["category"] == "Food"

    def test_valid_post_stores_correct_date(self, client):
        """The inserted row must have the submitted date."""
        client.post("/expenses/add", data=VALID_FORM)
        rows = _get_all_expenses(self.user_id)
        assert rows[0]["date"] == "2026-05-01"

    def test_valid_post_stores_correct_description(self, client):
        """The inserted row must have the submitted description."""
        client.post("/expenses/add", data=VALID_FORM)
        rows = _get_all_expenses(self.user_id)
        assert rows[0]["description"] == "Test lunch"

    def test_valid_post_stores_session_user_id(self, client):
        """The inserted expense's user_id must match the logged-in user's session id."""
        client.post("/expenses/add", data=VALID_FORM)
        rows = _get_all_expenses(self.user_id)
        assert rows[0]["user_id"] == self.user_id

    def test_valid_post_with_empty_description_succeeds(self, client):
        """Description is optional; omitting it must still result in a successful insert."""
        form = {**VALID_FORM, "description": ""}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 302
        assert _expense_count(self.user_id) == 1

    def test_expense_appears_on_profile_page_after_insert(self, client):
        """After a successful POST, the expense description must appear on /profile."""
        client.post("/expenses/add", data=VALID_FORM, follow_redirects=False)
        response = client.get("/profile")
        assert b"Test lunch" in response.data

    def test_valid_post_follows_redirect_to_profile_page(self, client):
        """Following the redirect after a valid POST must land on the profile page (200)."""
        response = client.post("/expenses/add", data=VALID_FORM, follow_redirects=True)
        assert response.status_code == 200

    def test_all_seven_categories_are_individually_accepted(self, client):
        """Each of the seven valid categories must be accepted without error."""
        before = _expense_count(self.user_id)
        for cat in VALID_CATEGORIES:
            form = {**VALID_FORM, "category": cat}
            response = client.post("/expenses/add", data=form)
            assert response.status_code == 302, (
                f"Category '{cat}' was unexpectedly rejected"
            )
        assert _expense_count(self.user_id) == before + len(VALID_CATEGORIES)

    def test_user_id_comes_from_session_not_form(self, client):
        """The expense must be linked to the session user even if a different user_id
        is injected in the form payload."""
        # Seed a second user so there is a valid alternative user_id to try injecting
        other_user_id = seed_user(
            name="Other User", email="other@example.com", password="password123"
        )
        # Try submitting with another user's id embedded in the form data
        form = {**VALID_FORM, "user_id": str(other_user_id)}
        client.post("/expenses/add", data=form)
        rows = _get_all_expenses(self.user_id)
        # The row must belong to the logged-in user, not the injected id
        assert len(rows) == 1
        assert rows[0]["user_id"] == self.user_id


# ---------------------------------------------------------------------------
# Validation: Amount
# ---------------------------------------------------------------------------

class TestAmountValidation:
    """Invalid amounts must show an inline error and must not insert any rows."""

    @pytest.fixture(autouse=True)
    def logged_in_user(self, client):
        self.user_id = seed_user()
        login_user(client)

    def test_missing_amount_returns_200_not_redirect(self, client):
        """Submitting without an amount must re-render the form (not redirect)."""
        form = {**VALID_FORM, "amount": ""}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 200

    def test_missing_amount_shows_error_message(self, client):
        """An inline error must appear when amount is missing."""
        form = {**VALID_FORM, "amount": ""}
        response = client.post("/expenses/add", data=form)
        assert b"error" in response.data.lower() or b"amount" in response.data

    def test_missing_amount_inserts_no_rows(self, client):
        """No expense row must be inserted when amount is missing."""
        form = {**VALID_FORM, "amount": ""}
        client.post("/expenses/add", data=form)
        assert _expense_count(self.user_id) == 0

    def test_zero_amount_returns_200_not_redirect(self, client):
        """Submitting zero as the amount must re-render the form (not redirect)."""
        form = {**VALID_FORM, "amount": "0"}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 200

    def test_zero_amount_shows_error_message(self, client):
        """An inline error must appear when amount is zero."""
        form = {**VALID_FORM, "amount": "0"}
        response = client.post("/expenses/add", data=form)
        assert b"error" in response.data.lower() or b"positive" in response.data.lower()

    def test_zero_amount_inserts_no_rows(self, client):
        """No expense row must be inserted when amount is zero."""
        form = {**VALID_FORM, "amount": "0"}
        client.post("/expenses/add", data=form)
        assert _expense_count(self.user_id) == 0

    def test_negative_amount_returns_200_not_redirect(self, client):
        """Submitting a negative amount must re-render the form (not redirect)."""
        form = {**VALID_FORM, "amount": "-10"}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 200

    def test_negative_amount_shows_error_message(self, client):
        """An inline error must appear when amount is negative."""
        form = {**VALID_FORM, "amount": "-10"}
        response = client.post("/expenses/add", data=form)
        assert b"error" in response.data.lower() or b"positive" in response.data.lower()

    def test_negative_amount_inserts_no_rows(self, client):
        """No expense row must be inserted when amount is negative."""
        form = {**VALID_FORM, "amount": "-10"}
        client.post("/expenses/add", data=form)
        assert _expense_count(self.user_id) == 0

    def test_non_numeric_amount_returns_200_not_redirect(self, client):
        """Submitting a non-numeric amount must re-render the form (not redirect)."""
        form = {**VALID_FORM, "amount": "abc"}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 200

    def test_non_numeric_amount_shows_error_message(self, client):
        """An inline error must appear when amount is not a number."""
        form = {**VALID_FORM, "amount": "abc"}
        response = client.post("/expenses/add", data=form)
        assert b"error" in response.data.lower() or b"amount" in response.data

    def test_non_numeric_amount_inserts_no_rows(self, client):
        """No expense row must be inserted when amount is not a number."""
        form = {**VALID_FORM, "amount": "abc"}
        client.post("/expenses/add", data=form)
        assert _expense_count(self.user_id) == 0

    def test_zero_decimal_amount_is_rejected(self, client):
        """0.00 must be treated as zero and rejected with an error."""
        form = {**VALID_FORM, "amount": "0.00"}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 200
        assert _expense_count(self.user_id) == 0


# ---------------------------------------------------------------------------
# Validation: Category
# ---------------------------------------------------------------------------

class TestCategoryValidation:
    """Categories outside the fixed set must be rejected."""

    @pytest.fixture(autouse=True)
    def logged_in_user(self, client):
        self.user_id = seed_user()
        login_user(client)

    def test_invalid_category_returns_200_not_redirect(self, client):
        """Submitting an unrecognised category must re-render the form (not redirect)."""
        form = {**VALID_FORM, "category": "Gadgets"}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 200

    def test_invalid_category_shows_error_message(self, client):
        """An inline error must appear when the category is not in the allowed set."""
        form = {**VALID_FORM, "category": "Gadgets"}
        response = client.post("/expenses/add", data=form)
        assert b"error" in response.data.lower() or b"category" in response.data

    def test_invalid_category_inserts_no_rows(self, client):
        """No expense row must be inserted for an unrecognised category."""
        form = {**VALID_FORM, "category": "Gadgets"}
        client.post("/expenses/add", data=form)
        assert _expense_count(self.user_id) == 0

    def test_empty_category_returns_200_not_redirect(self, client):
        """Submitting no category at all must re-render the form (not redirect)."""
        form = {**VALID_FORM, "category": ""}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 200

    def test_empty_category_inserts_no_rows(self, client):
        """No expense row must be inserted when category is absent."""
        form = {**VALID_FORM, "category": ""}
        client.post("/expenses/add", data=form)
        assert _expense_count(self.user_id) == 0

    def test_category_is_case_sensitive(self, client):
        """Category matching is case-sensitive; 'food' (lower-case) must be rejected."""
        form = {**VALID_FORM, "category": "food"}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 200
        assert _expense_count(self.user_id) == 0

    def test_category_with_extra_whitespace_is_rejected(self, client):
        """'Food ' (trailing space) is not in the allowed set and must be rejected."""
        form = {**VALID_FORM, "category": "Food "}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 200
        assert _expense_count(self.user_id) == 0


# ---------------------------------------------------------------------------
# Validation: Date
# ---------------------------------------------------------------------------

class TestDateValidation:
    """Dates that do not conform to YYYY-MM-DD must be rejected."""

    @pytest.fixture(autouse=True)
    def logged_in_user(self, client):
        self.user_id = seed_user()
        login_user(client)

    def test_missing_date_returns_200_not_redirect(self, client):
        """Submitting without a date must re-render the form (not redirect)."""
        form = {**VALID_FORM, "date": ""}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 200

    def test_missing_date_shows_error_message(self, client):
        """An inline error must appear when the date is absent."""
        form = {**VALID_FORM, "date": ""}
        response = client.post("/expenses/add", data=form)
        assert b"error" in response.data.lower() or b"date" in response.data

    def test_missing_date_inserts_no_rows(self, client):
        """No expense row must be inserted when date is missing."""
        form = {**VALID_FORM, "date": ""}
        client.post("/expenses/add", data=form)
        assert _expense_count(self.user_id) == 0

    def test_date_with_slashes_rejected(self, client):
        """A date using slashes (2026/05/01) instead of dashes must be rejected."""
        form = {**VALID_FORM, "date": "2026/05/01"}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 200
        assert _expense_count(self.user_id) == 0

    def test_date_with_slashes_shows_error_message(self, client):
        """An inline error must appear for a slash-delimited date."""
        form = {**VALID_FORM, "date": "2026/05/01"}
        response = client.post("/expenses/add", data=form)
        assert b"error" in response.data.lower() or b"date" in response.data

    def test_partial_date_rejected(self, client):
        """A partial date string like '2026-05' must be rejected."""
        form = {**VALID_FORM, "date": "2026-05"}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 200
        assert _expense_count(self.user_id) == 0

    def test_date_text_string_rejected(self, client):
        """A plaintext non-date string like 'yesterday' must be rejected."""
        form = {**VALID_FORM, "date": "yesterday"}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 200
        assert _expense_count(self.user_id) == 0

    def test_date_text_string_shows_error_message(self, client):
        """An inline error must appear for a non-date text string."""
        form = {**VALID_FORM, "date": "yesterday"}
        response = client.post("/expenses/add", data=form)
        assert b"error" in response.data.lower() or b"date" in response.data

    def test_invalid_calendar_date_rejected(self, client):
        """A structurally valid but calendrically impossible date (Feb 30) must be
        rejected because datetime.strptime raises ValueError for it."""
        form = {**VALID_FORM, "date": "2026-02-30"}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 200
        assert _expense_count(self.user_id) == 0

    def test_valid_iso_date_accepted(self, client):
        """A well-formed YYYY-MM-DD date must be accepted as valid."""
        form = {**VALID_FORM, "date": "2026-01-15"}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 302
        assert _expense_count(self.user_id) == 1


# ---------------------------------------------------------------------------
# Form Value Preservation on Validation Failure
# ---------------------------------------------------------------------------

class TestFormValuePreservation:
    """When validation fails, previously entered values must be re-rendered in the form."""

    @pytest.fixture(autouse=True)
    def logged_in_user(self, client):
        seed_user()
        login_user(client)

    def test_amount_preserved_on_invalid_category(self, client):
        """Amount entered by the user must reappear in the form after a category error."""
        form = {**VALID_FORM, "category": "InvalidCat"}
        response = client.post("/expenses/add", data=form)
        assert b"42.50" in response.data

    def test_category_preserved_on_invalid_amount(self, client):
        """Category selection must reappear in the form after an amount error."""
        form = {**VALID_FORM, "amount": "-5", "category": "Transport"}
        response = client.post("/expenses/add", data=form)
        assert b"Transport" in response.data

    def test_date_preserved_on_invalid_amount(self, client):
        """Entered date must reappear in the form after an amount error."""
        form = {**VALID_FORM, "amount": "0", "date": "2026-03-15"}
        response = client.post("/expenses/add", data=form)
        assert b"2026-03-15" in response.data

    def test_description_preserved_on_invalid_date(self, client):
        """Entered description must reappear in the form after a date error."""
        form = {**VALID_FORM, "date": "bad-date", "description": "my coffee run"}
        response = client.post("/expenses/add", data=form)
        assert b"my coffee run" in response.data

    def test_amount_preserved_on_invalid_date(self, client):
        """Amount entered must reappear in the form after a date error."""
        form = {**VALID_FORM, "amount": "99.99", "date": "not-a-date"}
        response = client.post("/expenses/add", data=form)
        assert b"99.99" in response.data

    def test_all_fields_preserved_on_invalid_category(self, client):
        """All submitted fields must be re-rendered when category validation fails."""
        form = {
            "amount": "15.00",
            "category": "BadCategory",
            "date": "2026-04-10",
            "description": "some purchase",
        }
        response = client.post("/expenses/add", data=form)
        html = response.data.decode()
        assert "15.00" in html
        assert "2026-04-10" in html
        assert "some purchase" in html


# ---------------------------------------------------------------------------
# User Isolation
# ---------------------------------------------------------------------------

class TestUserIsolation:
    """Expenses inserted by one user must not be visible to another user."""

    def test_expense_is_isolated_to_inserting_user(self, client):
        """An expense added by user A must not appear in user B's profile."""
        user_a_id = seed_user(name="User A", email="a@example.com", password="password123")
        user_b_id = seed_user(name="User B", email="b@example.com", password="password123")

        # Log in as user A and insert an expense
        login_user(client, email="a@example.com", password="password123")
        client.post(
            "/expenses/add",
            data={**VALID_FORM, "description": "user-a-only expense"},
        )

        # Verify the expense belongs only to user A in the DB
        a_rows = _get_all_expenses(user_a_id)
        b_rows = _get_all_expenses(user_b_id)
        assert len(a_rows) == 1
        assert len(b_rows) == 0

    def test_two_users_expenses_are_not_mixed(self, client):
        """Multiple users can add expenses; each sees only their own on /profile."""
        user_a_id = seed_user(name="User A", email="a@example.com", password="password123")
        user_b_id = seed_user(name="User B", email="b@example.com", password="password123")

        # User A adds an expense
        login_user(client, email="a@example.com", password="password123")
        client.post(
            "/expenses/add",
            data={**VALID_FORM, "description": "alpha-expense"},
        )

        # Log out user A, log in as user B
        client.get("/logout")
        login_user(client, email="b@example.com", password="password123")
        client.post(
            "/expenses/add",
            data={**VALID_FORM, "description": "beta-expense"},
        )

        # User B's profile must not contain User A's expense
        response = client.get("/profile")
        assert b"beta-expense" in response.data
        assert b"alpha-expense" not in response.data
