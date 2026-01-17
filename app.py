from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, time, os

app = Flask(__name__)
CORS(app)

DB_NAME = "users.db"

def get_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ---------- ENSURE USER ----------
def ensure_user(user_id, username=None, referrer_id=None):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    exists = c.fetchone()

    if not exists:
        c.execute("""
            INSERT INTO users (user_id, username, points, last_claim, referrer_id)
            VALUES (?, ?, 0, 0, ?)
        """, (user_id, username, referrer_id))
        conn.commit()

    conn.close()

# ---------- CLAIM ----------
@app.route("/claim", methods=["POST"])
def claim():
    data = request.get_json(force=True)

    user_id = data.get("user_id")
    username = data.get("username")
    referrer_id = data.get("referrer_id")

    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    ensure_user(user_id, username, referrer_id)

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT last_claim, referrer_id FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()

    now = int(time.time())

    # Cooldown check
    if now - row["last_claim"] < 86400:
        remaining = 86400 - (now - row["last_claim"])
        conn.close()
        return jsonify({"remaining": remaining}), 403

    # Update user claim
    c.execute("""
        UPDATE users
        SET points = points + 100, last_claim = ?
        WHERE user_id = ?
    """, (now, user_id))

    # Reward referrer ONLY ON FIRST CLAIM
    if row["referrer_id"] and row["last_claim"] == 0:
        c.execute("""
            UPDATE users
            SET points = points + 300
            WHERE user_id = ?
        """, (row["referrer_id"],))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "earned": 100})

# ---------- USER INFO ----------
@app.route("/me", methods=["POST"])
def me():
    data = request.get_json(force=True)
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    ensure_user(user_id)

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
    points = c.fetchone()["points"]

    c.execute("SELECT COUNT(*) FROM users WHERE referrer_id=?", (user_id,))
    referrals = c.fetchone()[0]

    conn.close()

    return jsonify({
        "points": points,
        "referrals": referrals
    })

# ---------- LEADERBOARD ----------
@app.route("/leaderboard", methods=["GET"])
def leaderboard():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT username, points
        FROM users
        WHERE username IS NOT NULL
        ORDER BY points DESC
        LIMIT 10
    """)

    rows = c.fetchall()
    conn.close()

    return jsonify([
        {
            "rank": i + 1,
            "username": row["username"],
            "points": row["points"]
        }
        for i, row in enumerate(rows)
    ])

# ---------- MAIN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
