import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import psycopg2
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
CORS(app)

# =========================
# CONFIG
# =========================

DATABASE_URL = os.environ.get("DATABASE_URL")

CLAIM_COOLDOWN_HOURS = 6

STAGES = {
    1: {"cost": 0, "reward": 100},
    2: {"cost": 1000, "reward": 150},
    3: {"cost": 3000, "reward": 220},
    4: {"cost": 7000, "reward": 320},
}

# =========================
# DATABASE
# =========================

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def get_or_create_user(telegram_id, username):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO users (telegram_id, username, points, stage)
        VALUES (%s, %s, 0, 1)
        ON CONFLICT (telegram_id)
        DO UPDATE SET username = EXCLUDED.username
        RETURNING telegram_id, username, points, stage, last_claim
        """,
        (telegram_id, username)
    )

    user = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return {
        "telegram_id": user[0],
        "username": user[1],
        "points": user[2],
        "stage": user[3] or 1,
        "last_claim": user[4],
    }

# =========================
# PAGES
# =========================

@app.route("/")
def preview():
    return render_template("preview.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

# =========================
# API
# =========================

@app.route("/api/user/<int:user_id>")
def get_user(user_id):
    username = request.args.get("username", "User")

    user = get_or_create_user(user_id, username)

    now = datetime.now(timezone.utc)
    last_claim = user["last_claim"]

    if last_claim:
        last_claim = last_claim.astimezone(timezone.utc)
        next_time = last_claim + timedelta(hours=CLAIM_COOLDOWN_HOURS)
        next_claim_in = max(0, int((next_time - now).total_seconds()))
    else:
        next_claim_in = 0

    return jsonify({
        "points": user["points"],
        "stage": user["stage"],
        "reward_per_claim": STAGES[user["stage"]]["reward"],
        "next_claim_in": next_claim_in
    })

@app.route("/api/claim", methods=["POST"])
def claim():
    data = request.get_json()
    telegram_id = data.get("user_id")
    username = data.get("username", "User")

    user = get_or_create_user(telegram_id, username)

    now = datetime.now(timezone.utc)
    last_claim = user["last_claim"]

    if last_claim:
        last_claim = last_claim.astimezone(timezone.utc)
        elapsed = now - last_claim
        if elapsed < timedelta(hours=CLAIM_COOLDOWN_HOURS):
            remaining = int((timedelta(hours=CLAIM_COOLDOWN_HOURS) - elapsed).total_seconds())
            return jsonify({
                "success": False,
                "message": "Claim not available yet",
                "next_claim_in": remaining
            })

    reward = STAGES[user["stage"]]["reward"]
    new_points = user["points"] + reward

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE users
        SET points = %s,
            last_claim = %s
        WHERE telegram_id = %s
        """,
        (new_points, now, telegram_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        "success": True,
        "points": new_points,
        "reward": reward,
        "next_claim_in": CLAIM_COOLDOWN_HOURS * 3600
    })

@app.route("/api/upgrade", methods=["POST"])
def upgrade():
    data = request.get_json()
    telegram_id = data.get("user_id")
    target_stage = int(data.get("target_stage"))

    if target_stage not in STAGES:
        return jsonify({"success": False, "message": "Invalid stage"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT points, stage FROM users WHERE telegram_id = %s",
        (telegram_id,)
    )
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return jsonify({"success": False, "message": "User not found"}), 404

    points, current_stage = row
    current_stage = current_stage or 1

    if target_stage <= current_stage:
        cur.close()
        conn.close()
        return jsonify({
            "success": False,
            "message": "Already upgraded"
        })

    cost = STAGES[target_stage]["cost"]

    if points < cost:
        cur.close()
        conn.close()
        return jsonify({
            "success": False,
            "message": "Insufficient points"
        })

    new_points = points - cost

    cur.execute(
        """
        UPDATE users
        SET points = %s,
            stage = %s
        WHERE telegram_id = %s
        """,
        (new_points, target_stage, telegram_id)
    )

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        "success": True,
        "stage": target_stage,
        "points": new_points,
        "reward_per_claim": STAGES[target_stage]["reward"]
    })

# =========================
# RUN
# =========================

if __name__ == "__main__":
    app.run(debug=True)
