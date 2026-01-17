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

def ensure_user(user_id, referrer_id=None):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    exists = c.fetchone()

    if not exists:
        c.execute(
            "INSERT INTO users (user_id, points, last_claim, referrer_id) VALUES (?, 0, 0, ?)",
            (user_id, referrer_id)
        )
        conn.commit()

    conn.close()

# ---------------- CLAIM ----------------
@app.route("/claim", methods=["POST"])
def claim():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    referrer_id = data.get("referrer_id")  # optional

    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    ensure_user(user_id, referrer_id)

    now = int(time.time())
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT last_claim FROM users WHERE user_id=?", (user_id,))
    last_claim = c.fetchone()["last_claim"]

    if now - last_claim < 86400:
        remaining = 86400 - (now - last_claim)
        conn.close()
        return jsonify({"remaining": remaining}), 403

    # Update user
    c.execute(
        "UPDATE users SET points = points + 100, last_claim=? WHERE user_id=?",
        (now, user_id)
    )

    # Reward referrer ON FIRST CLAIM ONLY
    c.execute("SELECT referrer_id, last_claim FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()

    if row["referrer_id"] and last_claim == 0:
        c.execute(
            "UPDATE users SET points = points + 300 WHERE user_id=?",
            (row["referrer_id"],)
        )

    conn.commit()
    conn.close()

    return jsonify({"success": True, "earned": 100})

# ---------------- USER INFO ----------------
@app.route("/me", methods=["POST"])
def me():
    data = request.get_json(force=True)
    user_id = data.get("user_id")

    ensure_user(user_id)

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
    points = c.fetchone()["points"]

    c.execute("SELECT COUNT(*) FROM users WHERE referrer_id=?", (user_id,))
    refs = c.fetchone()[0]

    conn.close()

    return jsonify({
        "points": points,
        "referrals": refs
    })

# ---------------- LEADERBOARD ----------------
@app.route("/leaderboard", methods=["GET"])
def leaderboard():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT user_id, points
        FROM users
        ORDER BY points DESC
        LIMIT 10
    """)

    rows = c.fetchall()
    conn.close()

    return jsonify([
        {
            "rank": i + 1,
            "user": row["user_id"],
            "points": row["points"]
        }
        for i, row in enumerate(rows)
    ])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
