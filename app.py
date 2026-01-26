import os
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import psycopg2
import psycopg2.extras

app = Flask(__name__, template_folder="templates")
CORS(app)

# -------------------------
# DATABASE CONNECTION
# -------------------------
def get_db():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        port=os.environ["DB_PORT"],
        sslmode="require"
    )

# -------------------------
# ROUTES (PAGES)
# -------------------------
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

# -------------------------
# API — GET OR CREATE USER
# -------------------------
@app.route("/api/user/<int:telegram_id>")
def get_user(telegram_id):
    username = request.args.get("username", "guest")

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        "SELECT telegram_id, username, points, last_claim FROM users WHERE telegram_id = %s",
        (telegram_id,)
    )
    user = cur.fetchone()

    if not user:
        cur.execute(
            """
            INSERT INTO users (telegram_id, username, points, last_claim)
            VALUES (%s, %s, 0, NULL)
            RETURNING telegram_id, username, points, last_claim
            """,
            (telegram_id, username)
        )
        user = cur.fetchone()
        conn.commit()

    cur.close()
    conn.close()

    next_claim = None
    if user["last_claim"]:
        next_claim = (user["last_claim"] + timedelta(hours=24)).isoformat()

    return jsonify({
        "telegram_id": user["telegram_id"],
        "username": user["username"],
        "points": user["points"],
        "next_claim": next_claim
    })

# -------------------------
# API — CLAIM (NO AUTO-CREATE)
# -------------------------
@app.route("/api/claim", methods=["POST"])
def claim():
    data = request.get_json()
    telegram_id = data.get("user_id")

    if not telegram_id:
        return jsonify({"error": "telegram_id required"}), 400

    now = datetime.now(timezone.utc)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        "SELECT points, last_claim FROM users WHERE telegram_id = %s",
        (telegram_id,)
    )
    user = cur.fetchone()

    if not user:
        cur.close()
        conn.close()
        return jsonify({"error": "User not found"}), 404

    if user["last_claim"]:
        next_claim_time = user["last_claim"] + timedelta(hours=24)
        if now < next_claim_time:
            cur.close()
            conn.close()
            return jsonify({
                "error": "Claim not available yet",
                "next_claim": next_claim_time.isoformat()
            }), 403

    new_points = user["points"] + 10

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
        "next_claim": (now + timedelta(hours=24)).isoformat()
    })
