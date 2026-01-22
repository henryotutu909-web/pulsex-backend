import os
from flask import Flask, render_template

# -------------------------------------------------
# FORCE ABSOLUTE PATHS (RENDER SAFE)
# -------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
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
# HEALTH CHECK (OPTIONAL, BUT USEFUL)
# -------------------------------------------------

@app.route("/health")
def health():
    return "OK"

# -------------------------------------------------
# LOCAL / RENDER ENTRY POINT
# -------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
