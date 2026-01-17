from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, time, os

app = Flask(__name__)
CORS(app)

DB_NAME = "users.db"

def get_db():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

@app.route("/claim", methods=["POST"])
def claim():
    data = request.get_json(force=True)
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    now = int(time.time())
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT last_claim FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()

    if not row:
        return jsonify({"error": "User not registered"}), 404

    if now - row[0] < 86400:
        remaining = 86400 - (now - row[0])
        return jsonify({"error": "Cooldown", "remaining": remaining}), 403

    c.execute(
        "UPDATE users SET points = points + 100, last_claim = ? WHERE user_id=?",
        (now, user_id)
    )

    conn.commit()
    conn.close()

    return jsonify({"success": True, "earned": 100})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
