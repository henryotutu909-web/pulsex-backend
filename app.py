from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import psycopg2
import os
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
CORS(app)

# ---------------- DB ----------------
def get_db():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        port=os.environ.get("DB_PORT", 5432)
    )

# ---------------- CONFIG ----------------
CLAIM_COOLDOWN = 6 * 60 * 60  # 6 hours

UPGRADE_TABLE = {
    1: {"cost": 500, "reward": 5},
    2: {"cost": 1000, "reward": 10},
    3: {"cost": 2500, "reward": 20},
}

# ---------------- PAGES ----------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/upgrade")
def upgrade_page():
    return render_template("upgrade.html")

# ---------------- API ----------------
@app.route("/api/user/<int:telegram_id>")
def get_user(telegram_id):
    username = request.args.get("username", "User")
    now = datetime.now(timezone.utc)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (telegram_id, username, points, level, reward)
        VALUES (%s, %s, 0, 1, 10)
        ON CONFLICT (telegram_id) DO NOTHING
    """, (telegram_id, username))

    cur.execute("""
        SELECT points, last_claim, level, reward
        FROM users WHERE telegram_id = %s
    """, (telegram_id,))

    points, last_claim, level, reward = cur.fetchone()

    next_claim_in = 0
    if last_claim:
        elapsed = (now - last_claim).total_seconds()
        next_claim_in = max(0, int(CLAIM_COOLDOWN - elapsed))

    cur.close()
    conn.close()

    return jsonify({
        "points": points,
        "level": level,
        "reward": reward,
        "next_claim_in": next_claim_in
    })

@app.route("/api/claim", methods=["POST"])
def claim():
    data = request.json
    telegram_id = data["user_id"]
    username = data.get("username", "User")
    now = datetime.now(timezone.utc)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (telegram_id, username, points, level, reward)
        VALUES (%s, %s, 0, 1, 10)
        ON CONFLICT (telegram_id) DO NOTHING
    """, (telegram_id, username))

    cur.execute("""
        SELECT points, last_claim, reward
        FROM users WHERE telegram_id = %s
    """, (telegram_id,))

    points, last_claim, reward = cur.fetchone()

    if last_claim and (now - last_claim).total_seconds() < CLAIM_COOLDOWN:
        remaining = CLAIM_COOLDOWN - (now - last_claim).total_seconds()
        return jsonify({"success": False, "next_claim_in": int(remaining)})

    points += reward

    cur.execute("""
        UPDATE users
        SET points = %s, last_claim = %s
        WHERE telegram_id = %s
    """, (points, now, telegram_id))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        "success": True,
        "points": points,
        "next_claim_in": CLAIM_COOLDOWN
    })

# ---------------- UPGRADE API ----------------
@app.route("/api/upgrade", methods=["POST"])
def upgrade():
    data = request.json
    telegram_id = data["user_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT points, level, reward
        FROM users WHERE telegram_id = %s
    """, (telegram_id,))

    row = cur.fetchone()
    if not row:
        return jsonify({"success": False, "message": "User not found"})

    points, level, reward = row

    if level not in UPGRADE_TABLE:
        return jsonify({"success": False, "message": "Max level reached"})

    upgrade = UPGRADE_TABLE[level]

    if points < upgrade["cost"]:
        return jsonify({"success": False, "message": "Not enough points"})

    new_points = points - upgrade["cost"]
    new_level = level + 1
    new_reward = reward + upgrade["reward"]

    cur.execute("""
        UPDATE users
        SET points = %s, level = %s, reward = %s
        WHERE telegram_id = %s
    """, (new_points, new_level, new_reward, telegram_id))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        "success": True,
        "points": new_points,
        "level": new_level,
        "reward": new_reward
    })

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run()
