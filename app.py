import os
import psycopg2
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify, render_template, redirect
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# =========================
# ROUTES
# =========================

@app.route("/")
def index():
    return redirect("/dashboard")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

# =========================
# API: GET USER
# =========================
@app.route("/api/user/<int:telegram_id>")
def get_user(telegram_id):
    username = request.args.get("username", "")

    conn = get_db()
    cur = conn.cursor()

    # Create user if not exists (ONLY existing columns)
    cur.execute("""
        INSERT INTO users (telegram_id, username, points, last_claim)
        VALUES (%s, %s, 0, NULL)
        ON CONFLICT (telegram_id) DO NOTHING
    """, (telegram_id, username))

    cur.execute("""
        SELECT points, last_claim
        FROM users
        WHERE telegram_id = %s
    """, (telegram_id,))

    points, last_claim = cur.fetchone()

    now = datetime.now(timezone.utc)

    if last_claim is None:
        next_claim_in = 0
    else:
        next_time = last_claim + timedelta(hours=6)
        next_claim_in = max(0, int((next_time - now).total_seconds()))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        "points": points,
        "next_claim_in": next_claim_in
    })

# =========================
# API: CLAIM
# =========================
@app.route("/api/claim", methods=["POST"])
def claim():
    data = request.json
    telegram_id = data["user_id"]

    CLAIM_REWARD = 10  # fixed, safe, matches old behavior

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT points, last_claim
        FROM users
        WHERE telegram_id = %s
        FOR UPDATE
    """, (telegram_id,))

    points, last_claim = cur.fetchone()
    now = datetime.now(timezone.utc)

    if last_claim and now - last_claim < timedelta(hours=6):
        next_claim_in = int((last_claim + timedelta(hours=6) - now).total_seconds())
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify(success=False, next_claim_in=next_claim_in)

    points += CLAIM_REWARD

    cur.execute("""
        UPDATE users
        SET points = %s, last_claim = %s
        WHERE telegram_id = %s
    """, (points, now, telegram_id))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify(
        success=True,
        points=points,
        next_claim_in=6 * 3600
    )

# =========================
# START
# =========================
if __name__ == "__main__":
    app.run(debug=True)
