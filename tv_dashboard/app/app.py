from flask import Flask, render_template, jsonify

from config import PROFILE, PAGE_ROTATE_SEC
from services.ha_client import HAClient
from services.transformer import transform


app = Flask(__name__)
ha = HAClient()
ha.start_polling()


@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        profile=PROFILE,
        page_rotate_sec=PAGE_ROTATE_SEC,
    )


@app.route("/api/data")
def api_data():
    snapshot = ha.snapshot()
    data = transform(snapshot)
    return jsonify(data)


@app.route("/healthz")
def healthz():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8765, debug=False)
