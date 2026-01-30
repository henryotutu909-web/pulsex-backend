import os
import psycopg2
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify, render_template, redirect
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# =========================
# DATABASE CONNECTION
# =========================
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

@app.route("/upgrade")
def upgrade_page():
    return render_template("upgrade.html")

# =========================
# API: GET USER
# =========================
@app.route("/api/user/<int:telegram_id>")
def get_user(telegram_id):
    username = request.args.get("username", "")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (telegram_id, username, points, reward, last_claim)
        VALUES (%s, %s, 0, 10, NULL)
        ON CONFLICT (telegram_id) DO NOTHING
    """, (telegram_id, username))

    cur.execute("""
        SELECT points, reward, last_claim
        FROM users
        WHERE telegram_id = %s
    """, (telegram_id,))

    points, reward, last_claim = cur.fetchone()

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
        "reward": reward,
        "next_claim_in": next_claim_in
    })

# =========================
# API: CLAIM
# =========================
@app.route("/api/claim", methods=["POST"])
def claim():
    data = request.json
    telegram_id = data["user_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT points, reward, last_claim
        FROM users
        WHERE telegram_id = %s
        FOR UPDATE
    """, (telegram_id,))

    points, reward, last_claim = cur.fetchone()
    now = datetime.now(timezone.utc)

    if last_claim and now - last_claim < timedelta(hours=6):
        next_claim_in = int((last_claim + timedelta(hours=6) - now).total_seconds())
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify(success=False, next_claim_in=next_claim_in)

    points += reward

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
# API: UPGRADE
# =========================
@app.route("/api/upgrade", methods=["POST"])
def upgrade():
    data = request.json
    telegram_id = data["user_id"]
    cost = data["cost"]
    reward_increase = data["reward_increase"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT points, reward
        FROM users
        WHERE telegram_id = %s
        FOR UPDATE
    """, (telegram_id,))

    points, reward = cur.fetchone()

    if points < cost:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify(success=False, message="Not enough points")

    points -= cost
    reward += reward_increase

    cur.execute("""
        UPDATE users
        SET points = %s, reward = %s
        WHERE telegram_id = %s
    """, (points, reward, telegram_id))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify(
        success=True,
        points=points,
        reward=reward
    )

# =========================
# START
# =========================
if __name__ == "__main__":
    app.run(debug=True)
