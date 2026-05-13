import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, session, request
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db, close_db

app = Flask(__name__)
app.secret_key = "dev-secret-change-in-prod"

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not name or not email or not password:
        return render_template("register.html", error="All fields are required.")

    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")

    password_hash = generate_password_hash(password)

    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return render_template("register.html", error="An account with that email already exists.")
    finally:
        close_db(conn)

    session["user_id"] = user_id
    session["user_name"] = name
    return redirect(url_for("profile"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("landing"))
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("login.html", error="All fields are required.")

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, name, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    finally:
        close_db(conn)

    if row is None or not check_password_hash(row["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session["user_id"] = row["id"]
    session["user_name"] = row["name"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


# ------------------------------------------------------------------ #
# Profile helpers — implemented in Step 05                            #
# ------------------------------------------------------------------ #

def _get_user(conn, user_id):
    row = conn.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    member_since = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S").strftime("%B %Y")
    return {"name": row["name"], "email": row["email"], "member_since": member_since}


def _build_date_clause(date_from, date_to):
    if date_from and date_to:
        return " AND date BETWEEN ? AND ?", (date_from, date_to)
    if date_from:
        return " AND date >= ?", (date_from,)
    if date_to:
        return " AND date <= ?", (date_to,)
    return "", ()


def _get_summary_stats(conn, user_id, date_from=None, date_to=None):
    clause, params = _build_date_clause(date_from, date_to)
    agg = conn.execute(
        f"SELECT SUM(amount) as total, COUNT(*) as cnt FROM expenses WHERE user_id = ?{clause}",
        (user_id,) + params,
    ).fetchone()
    total = agg["total"] or 0.0
    top_row = conn.execute(
        f"SELECT category FROM expenses WHERE user_id = ?{clause} "
        "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        (user_id,) + params,
    ).fetchone()
    return {
        "total_spent": f"₹{total:,.2f}",
        "transaction_count": agg["cnt"],
        "top_category": top_row["category"] if top_row else "—",
    }


def _get_transaction_history(conn, user_id, date_from=None, date_to=None):
    clause, params = _build_date_clause(date_from, date_to)
    limit = "" if (date_from or date_to) else " LIMIT 5"
    rows = conn.execute(
        f"SELECT amount, category, date, description "
        f"FROM expenses WHERE user_id = ?{clause} ORDER BY date DESC{limit}",
        (user_id,) + params,
    ).fetchall()
    return [
        {
            "date": datetime.strptime(r["date"], "%Y-%m-%d").strftime("%b %d"),
            "description": r["description"] or "",
            "category": r["category"],
            "amount": f"₹{r['amount']:,.2f}",
        }
        for r in rows
    ]


def _get_category_breakdown(conn, user_id, date_from=None, date_to=None):
    clause, params = _build_date_clause(date_from, date_to)
    rows = conn.execute(
        f"SELECT category, SUM(amount) as total FROM expenses "
        f"WHERE user_id = ?{clause} GROUP BY category ORDER BY total DESC",
        (user_id,) + params,
    ).fetchall()
    grand_total = sum(r["total"] for r in rows)
    return [
        {
            "name": r["category"],
            "total": f"₹{r['total']:,.2f}",
            "percent": int(r["total"] / grand_total * 100) if grand_total else 0,
        }
        for r in rows
    ]


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    user_id = session["user_id"]

    def _parse_date(val):
        if not val:
            return None
        try:
            datetime.strptime(val, "%Y-%m-%d")
            return val
        except ValueError:
            return None

    date_from = _parse_date(request.args.get("from"))
    date_to   = _parse_date(request.args.get("to"))

    today = datetime.today()
    this_month_from = today.replace(day=1).strftime("%Y-%m-%d")
    this_month_to   = today.strftime("%Y-%m-%d")
    last_3m_from    = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    last_3m_to      = today.strftime("%Y-%m-%d")

    if date_from is None and date_to is None:
        active_period = "All Time"
        showing_label = "All Time"
    elif date_from == this_month_from and date_to == this_month_to:
        active_period = "This Month"
        showing_label = today.strftime("%B %Y")
    elif date_from == last_3m_from and date_to == last_3m_to:
        active_period = "Last 3 Months"
        showing_label = f"{(today - timedelta(days=90)).strftime('%b %d, %Y')} – {today.strftime('%b %d, %Y')}"
    else:
        active_period = "Custom"
        parts = [p for p in [date_from, date_to] if p]
        showing_label = " – ".join(parts)

    url_this_month = url_for("profile", **{"from": this_month_from, "to": this_month_to})
    url_last_3m    = url_for("profile", **{"from": last_3m_from, "to": last_3m_to})
    url_all_time   = url_for("profile")

    conn = get_db()
    try:
        user         = _get_user(conn, user_id)
        stats        = _get_summary_stats(conn, user_id, date_from, date_to)
        transactions = _get_transaction_history(conn, user_id, date_from, date_to)
        categories   = _get_category_breakdown(conn, user_id, date_from, date_to)
    finally:
        close_db(conn)
    return render_template("profile.html",
                           user=user, stats=stats,
                           transactions=transactions,
                           categories=categories,
                           date_from=date_from,
                           date_to=date_to,
                           active_period=active_period,
                           showing_label=showing_label,
                           url_this_month=url_this_month,
                           url_last_3m=url_last_3m,
                           url_all_time=url_all_time)


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
