import os
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

# ------------------ CONFIG ------------------

CLAIM_COOLDOWN_HOURS = 6
CLAIM_REWARD = 10

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

app = Flask(__name__, template_folder="templates")
CORS(app)

# ------------------ DB ------------------

def get_db():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor,
        sslmode="require"
    )

# ------------------ USER HELPERS ------------------

def get_or_create_user(telegram_id: str, username: str | None):
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT telegram_id, username, points, last_claim
                    FROM users
                    WHERE telegram_id = %s
                    """,
                    (telegram_id,)
                )
                user = cur.fetchone()

                if user:
                    return user

                cur.execute(
                    """
                    INSERT INTO users (telegram_id, username, points, last_claim)
                    VALUES (%s, %s, 0, NULL)
                    RETURNING telegram_id, username, points, last_claim
                    """,
                    (telegram_id, username)
                )
                return cur.fetchone()
    finally:
        conn.close()

# ------------------ ROUTES ------------------

@app.route("/")
def preview():
    return render_template("preview.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/user/<telegram_id>")
def get_user(telegram_id):
    username = request.args.get("username")

    user = get_or_create_user(telegram_id, username)

    now = datetime.now(timezone.utc)

    if user["last_claim"] is None:
        next_claim_in = 0
    else:
        next_time = user["last_claim"] + timedelta(hours=CLAIM_COOLDOWN_HOURS)
        next_claim_in = max(0, int((next_time - now).total_seconds()))

    return jsonify({
        "telegram_id": user["telegram_id"],
        "username": user["username"],
        "points": user["points"],
        "next_claim_in": next_claim_in
    })

@app.route("/api/claim", methods=["POST"])
def claim():
    data = request.get_json(force=True)
    telegram_id = str(data.get("user_id"))
    username = data.get("username")

    if not telegram_id:
        return jsonify({"error": "Missing user_id"}), 400

    now = datetime.now(timezone.utc)

    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT telegram_id, points, last_claim
                    FROM users
                    WHERE telegram_id = %s
                    FOR UPDATE
                    """,
                    (telegram_id,)
                )
                user = cur.fetchone()

                if not user:
                    cur.execute(
                        """
                        INSERT INTO users (telegram_id, username, points, last_claim)
                        VALUES (%s, %s, 0, NULL)
                        RETURNING telegram_id, points, last_claim
                        """,
                        (telegram_id, username)
                    )
                    user = cur.fetchone()

                last_claim = user["last_claim"]

                if last_claim is not None:
                    elapsed = now - last_claim
                    if elapsed < timedelta(hours=CLAIM_COOLDOWN_HOURS):
                        remaining = int(
                            (timedelta(hours=CLAIM_COOLDOWN_HOURS) - elapsed).total_seconds()
                        )
                        return jsonify({
                            "success": False,
                            "message": "Claim not available yet",
                            "next_claim_in": remaining
                        })

                new_points = user["points"] + CLAIM_REWARD

                cur.execute(
                    """
                    UPDATE users
                    SET points = %s,
                        last_claim = %s
                    WHERE telegram_id = %s
                    """,
                    (new_points, now, telegram_id)
                )

                return jsonify({
                    "success": True,
                    "points": new_points,
                    "next_claim_in": CLAIM_COOLDOWN_HOURS * 3600
                })
    finally:
        conn.close()

# ------------------ RUN ------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
