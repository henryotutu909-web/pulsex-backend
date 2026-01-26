import os
from datetime import datetime, timedelta, timezone

import psycopg2
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ---------------- DB ----------------
def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"])

def get_or_create_user(telegram_id):
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
            INSERT INTO users (telegram_id, points, last_claim)
            VALUES (%s, 0, NULL)
            RETURNING telegram_id, points, last_claim
            """,
            (telegram_id,)
        )
        conn.commit()
        user = cur.fetchone()

    cur.close()
    conn.close()
    return user

# ---------------- PAGES ----------------
@app.route("/")
def preview():
    return render_template("preview.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

# ---------------- API ----------------
@app.route("/api/user/<telegram_id>")
def api_user(telegram_id):
    user = get_or_create_user(telegram_id)
    telegram_id, points, last_claim = user

    next_claim = None
    if last_claim:
        next_claim = last_claim + timedelta(hours=24)

    return jsonify({
        "telegram_id": telegram_id,
        "points": points,
        "next_claim": next_claim.isoformat() if next_claim else None
    })

@app.route("/api/claim", methods=["POST"])
def claim():
    data = request.json or {}
    telegram_id = data.get("telegram_id") or data.get("user_id")

    if not telegram_id:
        return jsonify({"error": "telegram_id missing"}), 400

    user = get_or_create_user(telegram_id)
    _, points, last_claim = user

    now = datetime.now(timezone.utc)

    # 🔒 COOLDOWN CHECK (THE ONLY RULE)
    if last_claim and now < last_claim + timedelta(hours=24):
        return jsonify({
            "error": "Claim not available yet",
            "next_claim": (last_claim + timedelta(hours=24)).isoformat()
        }), 400

    new_points = points + 100

    conn = get_db()
    cur = conn.cursor()
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
        "success": True,
        "points": new_points,
        "next_claim": (now + timedelta(hours=24)).isoformat()
    })

# ---------------- START ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
