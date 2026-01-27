import os
import psycopg2
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ.get("DATABASE_URL")

# -------------------------
# DATABASE CONNECTION
# -------------------------
def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# -------------------------
# CREATE USER IF NOT EXISTS
# -------------------------
def get_or_create_user(telegram_id, username):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT telegram_id, points, last_claim FROM users WHERE telegram_id = %s",
        (telegram_id,)
    )
    user = cur.fetchone()

    if not user:
        cur.execute(
            """
            INSERT INTO users (telegram_id, username, points, last_claim)
            VALUES (%s, %s, 0, NULL)
            """,
            (telegram_id, username)
        )
        conn.commit()
        points = 0
        last_claim = None
    else:
        points = user[1]
        last_claim = user[2]

    cur.close()
    conn.close()
    return points, last_claim

# -------------------------
# HOME / PREVIEW
# -------------------------
@app.route("/")
def preview():
    return render_template("preview.html")

# -------------------------
# DASHBOARD
# -------------------------
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")
@app.route("/upgrade")
def upgrade():
    return render_template("upgrade.html")
@app.route("/battery")
def battery():
    return render_template("battery.html")

# -------------------------
# GET USER DATA
# -------------------------
@app.route("/api/user/<int:telegram_id>")
def get_user(telegram_id):
    username = request.args.get("username", "user")

    points, last_claim = get_or_create_user(telegram_id, username)

    now = datetime.utcnow()
    cooldown = timedelta(hours=6)

    if last_claim:
        next_time = last_claim + cooldown
        seconds_left = max(0, int((next_time - now).total_seconds()))
    else:
        seconds_left = 0

    return jsonify({
        "telegram_id": telegram_id,
        "username": username,
        "points": points,
        "next_claim_in": seconds_left
    })

# -------------------------
# CLAIM ENDPOINT
# -------------------------
@app.route("/api/claim", methods=["POST"])
def claim():
    data = request.json
    telegram_id = data.get("user_id")
    username = data.get("username", "user")

    if not telegram_id:
        return jsonify({"error": "Missing telegram ID"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT points, last_claim FROM users WHERE telegram_id = %s",
        (telegram_id,)
    )
    user = cur.fetchone()

    now = datetime.utcnow()
    cooldown = timedelta(hours=6)

    if user:
        points, last_claim = user

        if last_claim:
            elapsed = now - last_claim
            if elapsed < cooldown:
                remaining = int((cooldown - elapsed).total_seconds())
                cur.close()
                conn.close()
                return jsonify({
                    "success": False,
                    "message": "Claim not available yet",
                    "next_claim_in": remaining
                })
        new_points = points + 10
    else:
        new_points = 10

    cur.execute(
        """
        INSERT INTO users (telegram_id, username, points, last_claim)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (telegram_id)
        DO UPDATE SET
            points = EXCLUDED.points,
            last_claim = EXCLUDED.last_claim,
            username = EXCLUDED.username
        """,
        (telegram_id, username, new_points, now)
    )

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        "success": True,
        "points": new_points,
        "next_claim_in": int(cooldown.total_seconds())
    })

# -------------------------
# RUN LOCAL
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)


