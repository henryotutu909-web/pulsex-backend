from flask import Flask, jsonify, request, render_template, redirect
from flask_cors import CORS
import psycopg2
import os
from datetime import datetime, timedelta, timezone

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# -------------------- DATABASE --------------------
def get_db():
    return psycopg2.connect(
        os.environ["DATABASE_URL"]
    )

# -------------------- ROUTES --------------------
@app.route("/")
def index():
    return redirect("/dashboard")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")
    
@app.route("/upgrade")
def upgrade_page():
    return render_template("upgrade.html")


# -------------------- GET USER --------------------
@app.route("/api/user/<int:telegram_id>")
def get_user(telegram_id):
    username = request.args.get("username", "User")

    conn = get_db()
    cur = conn.cursor()

    # Ensure user exists (level defaults to 1)
    cur.execute("""
        INSERT INTO users (telegram_id, username, points, level, last_claim)
        VALUES (%s, %s, 0, 1, NULL)
        ON CONFLICT (telegram_id) DO NOTHING
    """, (telegram_id, username))

    conn.commit()

    cur.execute("""
        SELECT points, level, last_claim
        FROM users
        WHERE telegram_id = %s
    """, (telegram_id,))

    points, level, last_claim = cur.fetchone()

    # timezone normalization (DO NOT TOUCH)
    if last_claim and last_claim.tzinfo is None:
        last_claim = last_claim.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)

    if last_claim:
        next_time = last_claim + timedelta(hours=6)
        next_claim_in = max(0, int((next_time - now).total_seconds()))
    else:
        next_claim_in = 0

    # reward derived from level (NOT stored)
    reward = 10 + (level - 1) * 6

    cur.close()
    conn.close()

    return jsonify({
        "points": points,
        "level": level,
        "reward": reward,
        "next_claim_in": next_claim_in
    })

# -------------------- CLAIM --------------------
@app.route("/api/claim", methods=["POST"])
def claim():
    data = request.json
    telegram_id = data.get("user_id")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT points, level, last_claim
        FROM users
        WHERE telegram_id = %s
        FOR UPDATE
    """, (telegram_id,))

    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return jsonify({"success": False}), 400

    points, level, last_claim = row

    if last_claim and last_claim.tzinfo is None:
        last_claim = last_claim.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)

    if last_claim and (now - last_claim) < timedelta(hours=6):
        next_claim_in = int((last_claim + timedelta(hours=6) - now).total_seconds())
        cur.close()
        conn.close()
        return jsonify({
            "success": False,
            "next_claim_in": next_claim_in
        })

    reward = 10 + (level - 1) * 6
    new_points = points + reward

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
        "next_claim_in": 5 * 60 * 60
    })

# -------------------- UPGRADE --------------------
@app.route("/api/upgrade", methods=["POST"])
def upgrade():
    data = request.json
    telegram_id = data.get("user_id")
    target_stage = data.get("target_stage")

    if not telegram_id or not target_stage:
        return jsonify({"success": False, "message": "Invalid request"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT points, level
        FROM users
        WHERE telegram_id = %s
        FOR UPDATE
    """, (telegram_id,))

    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return jsonify({"success": False, "message": "User not found"}), 400

    points, level = row

    # ✅ Enforce ONE LEVEL AT A TIME
    if target_stage != level + 1:
        cur.close()
        conn.close()
        return jsonify({
            "success": False,
            "message": "You can only upgrade one level at a time"
        })

    # ✅ Max level cap
    if level >= 50:
        cur.close()
        conn.close()
        return jsonify({
            "success": False,
            "message": "Max level reached"
        })

    # ✅ Cost formula (scales nicely)
    upgrade_cost = 100 * (target_stage ** 2)

    if points < upgrade_cost:
        cur.close()
        conn.close()
        return jsonify({
            "success": False,
            "message": "Not enough PulseX",
            "needed": upgrade_cost
        })

    new_level = target_stage
    new_points = points - upgrade_cost
    new_reward = 10 + (new_level - 1) * 6

    cur.execute("""
        UPDATE users
        SET level = %s,
            points = %s
        WHERE telegram_id = %s
    """, (new_level, new_points, telegram_id))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        "success": True,
        "level": new_level,
        "points": new_points,
        "reward": new_reward
    })

# -------------------- RUN --------------------
if __name__ == "__main__":
    app.run(debug=True)




