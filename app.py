import os
import psycopg2
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

CLAIM_COOLDOWN_HOURS = 24
CLAIM_REWARD = 10


def get_db():
    return psycopg2.connect(
        os.environ["DATABASE_URL"],
        sslmode="require"
    )


# ---------- PAGES ----------
@app.route("/")
def preview():
    return render_template("preview.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/tasks")
def tasks():
    return render_template("tasks.html")


@app.route("/referrals")
def referrals():
    return render_template("referrals.html")


@app.route("/wallet")
def wallet():
    return render_template("wallet.html")


# ---------- API ----------
@app.route("/api/user/<int:telegram_id>")
def get_user(telegram_id):
    username = request.args.get("username", "user")

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO users (telegram_id, username, points)
        VALUES (%s, %s, 0)
        ON CONFLICT (telegram_id) DO NOTHING
        """,
        (telegram_id, username)
    )
    conn.commit()

    cur.execute(
        "SELECT points, last_claim FROM users WHERE telegram_id = %s",
        (telegram_id,)
    )
    points, last_claim = cur.fetchone()

    next_claim = None
    if last_claim:
        next_claim = last_claim + timedelta(hours=CLAIM_COOLDOWN_HOURS)

    cur.close()
    conn.close()

    return jsonify({
        "points": points,
        "next_claim": next_claim.isoformat() if next_claim else None
    })


@app.route("/api/claim", methods=["POST"])
def claim():
    data = request.get_json()
    telegram_id = data.get("user_id")

    if not telegram_id:
        return jsonify({"error": "Invalid user"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT points, last_claim FROM users WHERE telegram_id = %s",
        (telegram_id,)
    )
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return jsonify({"error": "User not found"}), 404

    points, last_claim = row
    now = datetime.utcnow()

    if last_claim and now < last_claim + timedelta(hours=CLAIM_COOLDOWN_HOURS):
        cur.close()
        conn.close()
        return jsonify({"error": "Claim not available yet"}), 403

    new_points = points + CLAIM_REWARD

    cur.execute(
        """
        UPDATE users
        SET points = %s, last_claim = %s
        WHERE telegram_id = %s
        """,
        (new_points, now, telegram_id)
    )

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        "points": new_points,
        "next_claim": (now + timedelta(hours=CLAIM_COOLDOWN_HOURS)).isoformat()
    })
