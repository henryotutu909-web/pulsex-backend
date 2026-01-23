import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import psycopg2

app = Flask(__name__)
CORS(app)

# ---------------------------
# DATABASE CONNECTION
# ---------------------------
def get_db():
    return psycopg2.connect(
        os.environ["DATABASE_URL"],
        sslmode="require"
    )

# ---------------------------
# HEALTH CHECK
# ---------------------------
@app.route("/health")
def health():
    return "OK"

# ---------------------------
# PAGES
# ---------------------------
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

# ---------------------------
# API: GET USER
# ---------------------------
@app.route("/api/user/<int:user_id>")
def get_user(user_id):
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "SELECT points, last_claim FROM users WHERE user_id=%s",
            (user_id,)
        )
        row = cur.fetchone()

        if row:
            points, last_claim = row
            next_claim = (
                last_claim + timedelta(hours=24)
                if last_claim else None
            )
        else:
            points = 0
            next_claim = None

        cur.close()
        conn.close()

        return jsonify({
            "points": points,
            "next_claim": next_claim.isoformat() if next_claim else None
        })

    except Exception as e:
        print("GET USER ERROR:", e)
        return jsonify({"error": "Service unavailable"}), 500

# ---------------------------
# API: CLAIM DAILY REWARD
# ---------------------------
@app.route("/api/claim", methods=["POST"])
def claim():
    try:
        data = request.json
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"error": "Invalid user"}), 400

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "SELECT points, last_claim FROM users WHERE user_id=%s",
            (user_id,)
        )
        row = cur.fetchone()

        now = datetime.utcnow()

        if row:
            points, last_claim = row

            if last_claim and now - last_claim < timedelta(hours=24):
                cur.close()
                conn.close()
                return jsonify({"error": "Too early"}), 403

            points += 10
            cur.execute(
                "UPDATE users SET points=%s, last_claim=%s WHERE user_id=%s",
                (points, now, user_id)
            )
        else:
            points = 10
            cur.execute(
                "INSERT INTO users (user_id, points, last_claim) VALUES (%s,%s,%s)",
                (user_id, points, now)
            )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "points": points,
            "next_claim": (now + timedelta(hours=24)).isoformat()
        })

    except Exception as e:
        print("CLAIM ERROR:", e)
        return jsonify({
            "error": "Service temporarily unavailable"
        }), 500

# ---------------------------
# RUN LOCAL
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
