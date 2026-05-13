"""
Tests for Step 06: Date Filter on the Profile Page
===================================================

Spec: .claude/specs/06-date-filter-profile.md

The /profile route accepts optional `from` and `to` query parameters
(ISO dates: YYYY-MM-DD) and filters summary stats, transaction history,
and category breakdown to that window.  When no params are supplied the
page shows all-time data, preserving the Step 05 behaviour.

Key spec rules under test:
- No query params  => all-time data, active_period == "All Time"
- ?from=X&to=Y     => only expenses in [X, Y] are counted
- "This Month"     => from=first day of current month, to=today
- "Last 3 Months"  => from=today-90 days, to=today
- Empty window     => ₹0.00 total, 0 transactions, no category rows, no error
- Malformed params => silently ignored, falls back to all-time
- Unauthenticated  => redirect to /login
- Parameterised queries => SQL injection attempt does not crash the page

Seeding strategy:
  All expense dates are computed relative to datetime.today() so that the
  "This Month" and "Last 3 Months" preset assertions remain correct
  regardless of when the test suite is run.
"""

import pytest
from datetime import datetime, timedelta

from conftest import seed_user, seed_expense, login_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def today_str():
    return datetime.today().strftime("%Y-%m-%d")


def this_month_from_str():
    return datetime.today().replace(day=1).strftime("%Y-%m-%d")


def last_3m_from_str():
    return (datetime.today() - timedelta(days=90)).strftime("%Y-%m-%d")


def date_offset(days: int) -> str:
    """Return today +/- `days` as YYYY-MM-DD string."""
    return (datetime.today() + timedelta(days=days)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Fixture: a logged-in user with a controlled set of expenses
#
#  Expense set (relative to today):
#    A:  today-5   days  Food         100.00   "recent food"
#    B:  today-20  days  Transport     50.00   "recent transport"
#    C:  today-60  days  Bills        200.00   "older bill"
#    D:  today-100 days  Health        80.00   "old health"
#
#  Window membership:
#    "This Month"    (from=1st of this month, to=today):
#        A is in if today-5 >= 1st of month (always true for day >= 6);
#        handled by seeding day-5 which is always within the current month
#        unless today is the 1st–5th — the test accounts for this with a
#        computed check.
#    "Last 3 Months" (from=today-90, to=today): A + B + C
#    All Time: A + B + C + D
# ---------------------------------------------------------------------------

@pytest.fixture
def seeded_client(client):
    """Yield a test client with a logged-in user and deterministic expenses."""
    user_id = seed_user()
    seed_expense(user_id, 100.00, "Food",      date_offset(-5),  "recent food")
    seed_expense(user_id, 50.00,  "Transport", date_offset(-20), "recent transport")
    seed_expense(user_id, 200.00, "Bills",     date_offset(-60), "older bill")
    seed_expense(user_id, 80.00,  "Health",    date_offset(-100), "old health")
    login_user(client)
    return client


# ---------------------------------------------------------------------------
# Auth Guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_unauthenticated_get_redirects_to_login(self, client):
        """GET /profile without a session must redirect to /login."""
        response = client.get("/profile")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_unauthenticated_get_with_date_params_redirects_to_login(self, client):
        """Date params must not bypass the auth check."""
        response = client.get("/profile?from=2026-01-01&to=2026-12-31")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# All-Time (no query params)
# ---------------------------------------------------------------------------

class TestAllTime:
    def test_no_params_returns_200(self, seeded_client):
        """GET /profile with no date params must return HTTP 200."""
        response = seeded_client.get("/profile")
        assert response.status_code == 200

    def test_no_params_shows_all_four_expenses_total(self, seeded_client):
        """All-time total must be the sum of all four seeded expenses (₹430.00)."""
        response = seeded_client.get("/profile")
        assert b"\xe2\x82\xb9430.00" in response.data  # ₹430.00 in UTF-8

    def test_no_params_shows_all_time_showing_label(self, seeded_client):
        """The 'Showing:' subtitle must read 'All Time' when no params given."""
        response = seeded_client.get("/profile")
        assert b"Showing: All Time" in response.data

    def test_no_params_all_time_preset_button_is_active(self, seeded_client):
        """The 'All Time' preset button must carry the 'active' CSS class."""
        response = seeded_client.get("/profile")
        html = response.data.decode()
        # Template: class="filter-btn active" on the All Time anchor
        assert 'All Time' in html
        # Find the anchor for All Time and assert it has class active
        idx = html.index("All Time")
        # Walk back to the nearest opening <a tag
        tag_start = html.rfind("<a", 0, idx)
        tag_end = html.index(">", tag_start)
        tag_text = html[tag_start:tag_end]
        assert "active" in tag_text

    def test_no_params_transaction_count_is_four(self, seeded_client):
        """All-time view must show 4 in the Transactions stat card."""
        response = seeded_client.get("/profile")
        assert b"<span class=\"stat-value\">4</span>" in response.data

    def test_no_params_all_four_transactions_present_in_history(self, seeded_client):
        """All descriptions from the four seeded expenses must appear in the table."""
        response = seeded_client.get("/profile")
        assert b"recent food" in response.data
        assert b"recent transport" in response.data
        assert b"older bill" in response.data
        assert b"old health" in response.data

    def test_no_params_all_four_categories_in_breakdown(self, seeded_client):
        """Category breakdown must list Food, Transport, Bills, and Health."""
        response = seeded_client.get("/profile")
        assert b"Food" in response.data
        assert b"Transport" in response.data
        assert b"Bills" in response.data
        assert b"Health" in response.data

    def test_no_params_top_category_is_bills(self, seeded_client):
        """Bills (₹200) is the highest-spend category and must appear as top category."""
        response = seeded_client.get("/profile")
        # The stat card for top category must contain Bills
        html = response.data.decode()
        top_label_idx = html.index("Top Category")
        stat_value_start = html.index("stat-value", top_label_idx)
        stat_snippet = html[stat_value_start: stat_value_start + 60]
        assert "Bills" in stat_snippet


# ---------------------------------------------------------------------------
# Custom Date Range via ?from= and ?to=
# ---------------------------------------------------------------------------

class TestCustomDateRange:
    def test_exact_range_filters_total_correctly(self, seeded_client):
        """?from and ?to spanning only the two recent expenses must total ₹150.00."""
        from_date = date_offset(-25)   # catches day-20 and day-5 expenses
        to_date   = today_str()        # up to today
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        assert response.status_code == 200
        assert b"\xe2\x82\xb9150.00" in response.data  # ₹150.00 = 100 + 50

    def test_exact_range_transaction_count_is_two(self, seeded_client):
        """A range covering only the two recent expenses must show count=2."""
        from_date = date_offset(-25)
        to_date   = today_str()
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        assert b"<span class=\"stat-value\">2</span>" in response.data

    def test_exact_range_shows_matching_descriptions(self, seeded_client):
        """The transaction table must include descriptions inside the range."""
        from_date = date_offset(-25)
        to_date   = today_str()
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        assert b"recent food" in response.data
        assert b"recent transport" in response.data

    def test_exact_range_excludes_out_of_range_descriptions(self, seeded_client):
        """Expenses outside the date range must not appear in the transaction table."""
        from_date = date_offset(-25)
        to_date   = today_str()
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        assert b"older bill" not in response.data
        assert b"old health" not in response.data

    def test_exact_range_category_breakdown_limited_to_in_range(self, seeded_client):
        """Category breakdown must only include categories with in-range expenses."""
        from_date = date_offset(-25)
        to_date   = today_str()
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        # Bills and Health are outside this range
        html = response.data.decode()
        # The cat-name spans inside the category list must not mention Bills/Health
        # We verify by checking cat-list content; simple substring check is sufficient
        # since the template only renders cat.name inside <span class="cat-name">
        assert "Bills" not in _extract_category_list(html)
        assert "Health" not in _extract_category_list(html)

    def test_from_only_filters_with_open_upper_bound(self, seeded_client):
        """?from= with no ?to= must include all expenses on or after that date."""
        from_date = date_offset(-65)   # captures day-60, day-20, day-5
        response = seeded_client.get(f"/profile?from={from_date}")
        assert response.status_code == 200
        assert b"older bill" in response.data
        assert b"recent food" in response.data
        # day-100 expense is before the from date — must be excluded
        assert b"old health" not in response.data

    def test_to_only_filters_with_open_lower_bound(self, seeded_client):
        """?to= with no ?from= must include all expenses up to and including that date."""
        to_date = date_offset(-70)     # only captures day-100 expense
        response = seeded_client.get(f"/profile?to={to_date}")
        assert response.status_code == 200
        assert b"old health" in response.data
        # All expenses newer than day-70 must be excluded
        assert b"recent food" not in response.data
        assert b"older bill" not in response.data

    def test_custom_range_showing_label_contains_dates(self, seeded_client):
        """The 'Showing:' subtitle for a custom range must include the date strings."""
        from_date = "2025-01-01"
        to_date   = "2025-03-31"
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        html = response.data.decode()
        assert "2025-01-01" in html
        assert "2025-03-31" in html

    def test_filtered_view_no_limit_cap_on_transactions(self, seeded_client):
        """When a date filter is active, all matching rows are shown (no LIMIT 5 cap)."""
        # Seed 7 more expenses within a tight known range so the total is > 5
        conn = _get_test_conn()
        user_row = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        user_id = user_row["id"]
        descriptions = [f"extra-{i}" for i in range(6)]
        for desc in descriptions:
            seed_expense(user_id, 10.00, "Food", date_offset(-3), desc)

        from_date = date_offset(-4)
        to_date   = today_str()
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        html = response.data.decode()
        # All 6 extra descriptions must be present (proving LIMIT 5 was removed)
        for desc in descriptions:
            assert desc in html


# ---------------------------------------------------------------------------
# "This Month" Preset
# ---------------------------------------------------------------------------

class TestThisMonthPreset:
    def test_this_month_preset_link_present_in_page(self, seeded_client):
        """The rendered page must contain an anchor with text 'This Month'."""
        response = seeded_client.get("/profile")
        assert b"This Month" in response.data

    def test_this_month_url_returns_200(self, seeded_client):
        """GET /profile with this-month params must return HTTP 200."""
        from_date = this_month_from_str()
        to_date   = today_str()
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        assert response.status_code == 200

    def test_this_month_active_period_button_has_active_class(self, seeded_client):
        """When this-month params match, the 'This Month' button must be active."""
        from_date = this_month_from_str()
        to_date   = today_str()
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        html = response.data.decode()
        idx = html.index("This Month")
        tag_start = html.rfind("<a", 0, idx)
        tag_end = html.index(">", tag_start)
        tag_text = html[tag_start:tag_end]
        assert "active" in tag_text

    def test_this_month_showing_label_is_month_year(self, seeded_client):
        """The showing label must be the current month name and year (e.g. 'May 2026')."""
        from_date = this_month_from_str()
        to_date   = today_str()
        expected_label = datetime.today().strftime("%B %Y")
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        assert expected_label.encode() in response.data

    def test_this_month_excludes_expenses_before_month_start(self, seeded_client):
        """Expenses older than 30 days are outside this month and must be excluded."""
        # day-60 ("older bill") and day-100 ("old health") are not in current month
        from_date = this_month_from_str()
        to_date   = today_str()
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        assert b"older bill" not in response.data
        assert b"old health" not in response.data

    def test_this_month_includes_expense_within_month(self, seeded_client):
        """An expense seeded 5 days ago must appear when within the current month."""
        today = datetime.today()
        # Only run this assertion if today is the 6th or later (day-5 is still this month)
        if today.day >= 6:
            from_date = this_month_from_str()
            to_date   = today_str()
            response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
            assert b"recent food" in response.data
        else:
            pytest.skip("Today is within the first 5 days of the month; day-5 expense falls in prior month")


# ---------------------------------------------------------------------------
# "Last 3 Months" Preset
# ---------------------------------------------------------------------------

class TestLast3MonthsPreset:
    def test_last_3m_preset_link_present_in_page(self, seeded_client):
        """The rendered page must contain an anchor with text 'Last 3 Months'."""
        response = seeded_client.get("/profile")
        assert b"Last 3 Months" in response.data

    def test_last_3m_url_returns_200(self, seeded_client):
        """GET /profile with last-3-months params must return HTTP 200."""
        from_date = last_3m_from_str()
        to_date   = today_str()
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        assert response.status_code == 200

    def test_last_3m_active_period_button_has_active_class(self, seeded_client):
        """When last-3m params match, the 'Last 3 Months' button must be active."""
        from_date = last_3m_from_str()
        to_date   = today_str()
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        html = response.data.decode()
        idx = html.index("Last 3 Months")
        tag_start = html.rfind("<a", 0, idx)
        tag_end = html.index(">", tag_start)
        tag_text = html[tag_start:tag_end]
        assert "active" in tag_text

    def test_last_3m_showing_label_is_range_string(self, seeded_client):
        """Showing label for Last 3 Months must contain both boundary dates."""
        from_date = last_3m_from_str()
        to_date   = today_str()
        today = datetime.today()
        expected_end = today.strftime("%b %d, %Y")
        expected_start = (today - timedelta(days=90)).strftime("%b %d, %Y")
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        html = response.data.decode()
        assert expected_start in html
        assert expected_end in html

    def test_last_3m_includes_expenses_within_90_days(self, seeded_client):
        """Expenses at day-5, day-20, and day-60 must all appear (within 90 days)."""
        from_date = last_3m_from_str()
        to_date   = today_str()
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        assert b"recent food" in response.data
        assert b"recent transport" in response.data
        assert b"older bill" in response.data

    def test_last_3m_excludes_expense_older_than_90_days(self, seeded_client):
        """The expense at day-100 is outside the 90-day window and must be excluded."""
        from_date = last_3m_from_str()
        to_date   = today_str()
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        assert b"old health" not in response.data

    def test_last_3m_total_is_350(self, seeded_client):
        """Total for the 3 in-window expenses must be ₹350.00 (100+50+200)."""
        from_date = last_3m_from_str()
        to_date   = today_str()
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        assert b"\xe2\x82\xb9350.00" in response.data  # ₹350.00 in UTF-8


# ---------------------------------------------------------------------------
# Empty Window (no matching expenses)
# ---------------------------------------------------------------------------

class TestEmptyDateRange:
    def test_empty_range_returns_200_without_error(self, seeded_client):
        """A date range with no expenses must not raise an error (HTTP 200)."""
        response = seeded_client.get("/profile?from=2000-01-01&to=2000-01-31")
        assert response.status_code == 200

    def test_empty_range_shows_zero_total(self, seeded_client):
        """Total spent for an empty range must be ₹0.00."""
        response = seeded_client.get("/profile?from=2000-01-01&to=2000-01-31")
        assert b"\xe2\x82\xb90.00" in response.data  # ₹0.00

    def test_empty_range_shows_zero_transaction_count(self, seeded_client):
        """Transaction count stat card must display 0 for an empty range."""
        response = seeded_client.get("/profile?from=2000-01-01&to=2000-01-31")
        assert b"<span class=\"stat-value\">0</span>" in response.data

    def test_empty_range_shows_dash_for_top_category(self, seeded_client):
        """Top category must show the em-dash placeholder when there are no expenses."""
        response = seeded_client.get("/profile?from=2000-01-01&to=2000-01-31")
        assert "—".encode("utf-8") in response.data

    def test_empty_range_has_no_category_rows(self, seeded_client):
        """The category breakdown list must have no <li> rows for an empty range."""
        response = seeded_client.get("/profile?from=2000-01-01&to=2000-01-31")
        html = response.data.decode()
        # The category list is inside <ul class="cat-list"> — verify no cat-row items
        assert "cat-row" not in html

    def test_empty_range_transaction_table_body_is_empty(self, seeded_client):
        """The transaction table must have an empty <tbody> for an empty range."""
        response = seeded_client.get("/profile?from=2000-01-01&to=2000-01-31")
        html = response.data.decode()
        tbody_start = html.index("<tbody>")
        tbody_end   = html.index("</tbody>", tbody_start)
        tbody_content = html[tbody_start + len("<tbody>"):tbody_end].strip()
        assert tbody_content == ""

    def test_empty_range_page_still_renders_filter_bar(self, seeded_client):
        """The filter bar must still be rendered even when no expenses match."""
        response = seeded_client.get("/profile?from=2000-01-01&to=2000-01-31")
        assert b"filter-btn" in response.data
        assert b"This Month" in response.data
        assert b"Last 3 Months" in response.data
        assert b"All Time" in response.data

    def test_empty_range_showing_label_contains_supplied_dates(self, seeded_client):
        """The showing label for an empty custom range must echo the supplied dates."""
        response = seeded_client.get("/profile?from=2000-01-01&to=2000-01-31")
        html = response.data.decode()
        assert "2000-01-01" in html
        assert "2000-01-31" in html


# ---------------------------------------------------------------------------
# Malformed / Invalid Query Parameters
# ---------------------------------------------------------------------------

class TestMalformedParams:
    def test_bad_from_param_returns_200(self, seeded_client):
        """A non-date ?from= value must not crash the page (HTTP 200)."""
        response = seeded_client.get("/profile?from=bad")
        assert response.status_code == 200

    def test_bad_to_param_returns_200(self, seeded_client):
        """A non-date ?to= value must not crash the page (HTTP 200)."""
        response = seeded_client.get("/profile?to=not-a-date")
        assert response.status_code == 200

    def test_bad_from_and_to_falls_back_to_all_time(self, seeded_client):
        """Both params malformed must silently fall back to all-time data."""
        response = seeded_client.get("/profile?from=bad&to=also-bad")
        assert response.status_code == 200
        # All-time total (₹430.00) must be present
        assert b"\xe2\x82\xb9430.00" in response.data

    def test_bad_from_shows_all_time_showing_label(self, seeded_client):
        """Malformed ?from= must fall back and show 'Showing: All Time'."""
        response = seeded_client.get("/profile?from=not-a-date")
        assert b"Showing: All Time" in response.data

    def test_bad_to_shows_all_time_showing_label(self, seeded_client):
        """Malformed ?to= must fall back and show 'Showing: All Time'."""
        response = seeded_client.get("/profile?to=2026/04/01")  # slashes, not dashes
        assert b"Showing: All Time" in response.data

    def test_partial_date_string_is_rejected(self, seeded_client):
        """A partial date like '2026-04' must be treated as malformed."""
        response = seeded_client.get("/profile?from=2026-04&to=2026-05")
        assert response.status_code == 200
        # Falls back to all-time
        assert b"Showing: All Time" in response.data

    def test_sql_injection_attempt_in_from_param_returns_200(self, seeded_client):
        """An SQL injection string in ?from= must be silently ignored (no crash)."""
        # The spec mandates parameterised queries; malformed input falls back to all-time
        payload = "' OR '1'='1"
        response = seeded_client.get(f"/profile?from={payload}")
        assert response.status_code == 200

    def test_sql_injection_shows_all_time_data(self, seeded_client):
        """After an injection attempt the page must display normal all-time data."""
        payload = "'; DROP TABLE expenses; --"
        response = seeded_client.get(f"/profile?from={payload}")
        assert response.status_code == 200
        # expenses table was not dropped — all-time total still present
        assert b"\xe2\x82\xb9430.00" in response.data

    def test_empty_string_from_param_falls_back_to_all_time(self, seeded_client):
        """?from= with an empty value must be treated as absent (all-time)."""
        response = seeded_client.get("/profile?from=&to=")
        assert response.status_code == 200
        assert b"Showing: All Time" in response.data


# ---------------------------------------------------------------------------
# Filter Bar Rendering
# ---------------------------------------------------------------------------

class TestFilterBarRendering:
    def test_profile_page_renders_filter_bar(self, seeded_client):
        """The profile page must include the date filter bar section."""
        response = seeded_client.get("/profile")
        assert b"profile-filter-bar" in response.data

    def test_filter_bar_has_three_preset_links(self, seeded_client):
        """The filter bar must render all three preset anchor links."""
        response = seeded_client.get("/profile")
        assert b"This Month" in response.data
        assert b"Last 3 Months" in response.data
        assert b"All Time" in response.data

    def test_filter_form_has_from_and_to_inputs(self, seeded_client):
        """The filter form must include date inputs named 'from' and 'to'."""
        response = seeded_client.get("/profile")
        assert b'name="from"' in response.data
        assert b'name="to"' in response.data

    def test_filter_form_method_is_get(self, seeded_client):
        """The filter form must use method GET (not POST)."""
        response = seeded_client.get("/profile")
        html = response.data.decode()
        form_start = html.index("filter-form")
        # Walk back to opening <form tag
        tag_start = html.rfind("<form", 0, form_start + len("filter-form"))
        tag_end = html.index(">", tag_start)
        form_tag = html[tag_start:tag_end].lower()
        assert 'method="get"' in form_tag

    def test_filter_form_action_points_to_profile(self, seeded_client):
        """The filter form action must point to the /profile URL."""
        response = seeded_client.get("/profile")
        html = response.data.decode()
        form_start = html.index("filter-form")
        tag_start = html.rfind("<form", 0, form_start + len("filter-form"))
        tag_end = html.index(">", tag_start)
        form_tag = html[tag_start:tag_end]
        assert "profile" in form_tag

    def test_filter_bar_has_showing_label(self, seeded_client):
        """The filter bar must display a 'Showing:' label."""
        response = seeded_client.get("/profile")
        assert b"Showing:" in response.data

    def test_date_inputs_pre_populated_with_active_params(self, seeded_client):
        """Active from/to params must be pre-filled into the date input values."""
        from_date = "2026-01-01"
        to_date   = "2026-03-31"
        response = seeded_client.get(f"/profile?from={from_date}&to={to_date}")
        html = response.data.decode()
        assert f'value="{from_date}"' in html
        assert f'value="{to_date}"' in html

    def test_preset_buttons_are_anchor_tags(self, seeded_client):
        """Spec requires preset buttons to be <a> elements, not <button> elements."""
        response = seeded_client.get("/profile")
        html = response.data.decode()
        # Each preset text must appear inside an <a ...> tag
        for preset in ("This Month", "Last 3 Months", "All Time"):
            idx = html.index(preset)
            tag_start = html.rfind("<", 0, idx)
            assert html[tag_start:].startswith("<a"), (
                f"Preset '{preset}' must be inside an <a> tag"
            )

    def test_filter_form_has_labels_for_accessibility(self, seeded_client):
        """The spec requires <label> elements for the date inputs (accessibility)."""
        response = seeded_client.get("/profile")
        assert b"<label" in response.data

    def test_only_one_preset_has_active_class_at_a_time(self, seeded_client):
        """At most one preset anchor should carry the 'active' CSS class."""
        response = seeded_client.get("/profile")
        html = response.data.decode()
        # Count occurrences of filter-btn active in the filter-presets block
        presets_start = html.index("filter-presets")
        presets_end   = html.index("</div>", presets_start)
        presets_block = html[presets_start:presets_end]
        active_count  = presets_block.count("active")
        assert active_count == 1, (
            f"Expected exactly 1 active preset, found {active_count}"
        )


# ---------------------------------------------------------------------------
# User Isolation
# ---------------------------------------------------------------------------

class TestUserIsolation:
    def test_date_filter_only_shows_current_users_expenses(self, client):
        """Filtered results must never include another user's expenses."""
        # Seed two users with expenses on the same date
        user1_id = seed_user(name="User One", email="one@example.com")
        user2_id = seed_user(name="User Two", email="two@example.com")

        date = date_offset(-5)
        seed_expense(user1_id, 999.00, "Food", date, "user1 private")
        seed_expense(user2_id, 111.00, "Food", date, "user2 private")

        # Log in as user2
        login_user(client, email="two@example.com")

        response = client.get(f"/profile?from={date}&to={date}")
        assert b"user2 private" in response.data
        assert b"user1 private" not in response.data


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_category_list(html: str) -> str:
    """Return the inner HTML of the <ul class="cat-list"> element."""
    try:
        start = html.index('class="cat-list"')
        ul_end = html.index("</ul>", start)
        return html[start:ul_end]
    except ValueError:
        return ""


def _get_test_conn():
    """Access the shared in-memory connection directly for seeding within tests."""
    from conftest import _get_test_db
    return _get_test_db()
