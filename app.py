from flask import Flask, jsonify, request, render_template, redirect
from flask_cors import CORS
import psycopg2
import os
from datetime import datetime, timedelta, timezone

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

COOLDOWN_SECONDS = 6 * 60 * 60  # 6 hours
CLAIM_REWARD = 10


# ✅ SINGLE DATABASE_URL CONNECTION (CORRECT)
def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require")


@app.route("/")
def index():
    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# ✅ LOAD USER + COUNTDOWN
@app.route("/api/user/<int:telegram_id>")
def get_user(telegram_id):
    username = request.args.get("username", "User")

    conn = get_db()
    cur = conn.cursor()

    # Ensure user exists (SAFE – NO EXTRA COLUMNS)
    cur.execute("""
        INSERT INTO users (telegram_id, username, points)
        VALUES (%s, %s, 0)
        ON CONFLICT (telegram_id) DO NOTHING
    """, (telegram_id, username))
    conn.commit()

    # Fetch user data
    cur.execute("""
        SELECT points, last_claim
        FROM users
        WHERE telegram_id = %s
    """, (telegram_id,))
    row = cur.fetchone()

    points = row[0]
    last_claim = row[1]

    now = datetime.now(timezone.utc)

    if last_claim is None:
        next_claim_in = 0
    else:
        last_claim = last_claim.replace(tzinfo=timezone.utc)
        elapsed = (now - last_claim).total_seconds()
        next_claim_in = max(0, int(COOLDOWN_SECONDS - elapsed))

    cur.close()
    conn.close()

    return jsonify({
        "points": points,
        "next_claim_in": next_claim_in
    })


# ✅ CLAIM ENDPOINT (STABLE)
@app.route("/api/claim", methods=["POST"])
def claim():
    data = request.json
    telegram_id = data.get("user_id")

    if not telegram_id:
        return jsonify({"success": False, "message": "Missing user"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT points, last_claim
        FROM users
        WHERE telegram_id = %s
    """, (telegram_id,))
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return jsonify({"success": False, "message": "User not found"}), 404

    points, last_claim = row
    now = datetime.now(timezone.utc)

    if last_claim:
        last_claim = last_claim.replace(tzinfo=timezone.utc)
        elapsed = (now - last_claim).total_seconds()
        if elapsed < COOLDOWN_SECONDS:
            remaining = int(COOLDOWN_SECONDS - elapsed)
            cur.close()
            conn.close()
            return jsonify({
                "success": False,
                "next_claim_in": remaining
            })

    # Apply reward
    new_points = points + CLAIM_REWARD

    cur.execute("""
        UPDATE users
        SET points = %s, last_claim = %s
        WHERE telegram_id = %s
    """, (new_points, now, telegram_id))
    conn.commit()

    cur.close()
    conn.close()

    return jsonify({
        "success": True,
        "points": new_points,
        "next_claim_in": COOLDOWN_SECONDS
    })


if __name__ == "__main__":
    app.run(debug=True)
