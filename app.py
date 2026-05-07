import sqlite3
from datetime import datetime
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
        conn.close()
        return render_template("register.html", error="An account with that email already exists.")

    conn.close()
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
    row = conn.execute(
        "SELECT id, name, password_hash FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    conn.close()

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


def _get_summary_stats(conn, user_id):
    agg = conn.execute(
        "SELECT SUM(amount) as total, COUNT(*) as cnt FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    total = agg["total"] or 0.0
    top_row = conn.execute(
        "SELECT category FROM expenses WHERE user_id = ? "
        "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    return {
        "total_spent": f"₹{total:,.2f}",
        "transaction_count": agg["cnt"],
        "top_category": top_row["category"] if top_row else "—",
    }


def _get_transaction_history(conn, user_id):
    rows = conn.execute(
        "SELECT amount, category, date, description "
        "FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT 5",
        (user_id,),
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


def _get_category_breakdown(conn, user_id):
    rows = conn.execute(
        "SELECT category, SUM(amount) as total FROM expenses "
        "WHERE user_id = ? GROUP BY category ORDER BY total DESC",
        (user_id,),
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
    conn = get_db()
    try:
        user         = _get_user(conn, user_id)
        stats        = _get_summary_stats(conn, user_id)
        transactions = _get_transaction_history(conn, user_id)
        categories   = _get_category_breakdown(conn, user_id)
    finally:
        close_db(conn)
    return render_template("profile.html",
                           user=user, stats=stats,
                           transactions=transactions,
                           categories=categories)


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
