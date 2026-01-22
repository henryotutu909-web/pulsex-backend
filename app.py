import os
from flask import Flask, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

print("BASE DIR:", BASE_DIR)
print("FILES IN BASE DIR:", os.listdir(BASE_DIR))

templates_path = os.path.join(BASE_DIR, "templates")
print("TEMPLATES PATH:", templates_path)

if os.path.exists(templates_path):
    print("FILES IN TEMPLATES:", os.listdir(templates_path))
else:
    print("❌ templates folder NOT FOUND")

app = Flask(
    __name__,
    template_folder=templates_path,
    static_folder=os.path.join(BASE_DIR, "static")
)

@app.route("/")
def preview():
    return render_template("preview.html")

@app.route("/health")
def health():
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
