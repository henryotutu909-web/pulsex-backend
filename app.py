import os
import psycopg2
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify

# -------------------------------------------------
# APP SETUP
# -------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

# -------------------------------------------------
# DATABASE CONNECTION
# -------------------------------------------------

import os
import psycopg2

def get_db():
    return psycopg2.connect(
        os.environ["DATABASE_URL"],
        sslmode="require"
    )


# -------------------------------------------------
# PAGE ROUTES
# -------------------------------------------------

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

# -------------------------------------------------
# API — USER STATE
# -------------------------------------------------

@app.route("/api/user/<int:user_id>")
def get_user(user_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "select points, last_claim from users where id=%s",
        (user_id,)
    )
    row = cur.fetchone()

    if not row:
        cur.execute(
            "insert into users (id, points) values (%s, 0)",
            (user_id,)
        )
        conn.commit()
        points = 0
        last_claim = None
    else:
        points, last_claim = row

    cur.close()
    conn.close()

    next_claim = (
        (last_claim + timedelta(hours=24)).isoformat()
        if last_claim else None
    )

    return jsonify({
        "points": points,
        "next_claim": next_claim
    })

# -------------------------------------------------
# API — CLAIM DAILY POINTS
# -------------------------------------------------

@app.route("/api/claim", methods=["POST"])
def claim():
    data = request.json
    user_id = data["user_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "select points, last_claim from users where id=%s",
        (user_id,)
    )
    row = cur.fetchone()

    now = datetime.utcnow()

    if row and row[1] and now < row[1] + timedelta(hours=24):
        cur.close()
        conn.close()
        return jsonify({"error": "Too early"}), 400

    if row:
        cur.execute(
            """
            update users
            set points = points + 10,
                last_claim = %s
            where id = %s
            """,
            (now, user_id)
        )
    else:
        cur.execute(
            """
            insert into users (id, points, last_claim)
            values (%s, 10, %s)
            """,
            (user_id, now)
        )

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True})

# -------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

