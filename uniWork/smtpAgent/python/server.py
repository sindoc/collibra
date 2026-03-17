"""
python/server.py — Singine smtpAgent web server
Serves the iPad-friendly compose UI and bridges POST /compose → Clojure SMTP service.

Architecture:
  Browser (iPad)  →  Flask :8080  →  Clojure :8026  →  SMTP

Config read from ../meta/config.edn (EDN parsed manually — no deps beyond stdlib + flask).
"""

import os
import re
import json
import logging
import requests
from flask import Flask, request, render_template, jsonify

# ── Logging ───────────────────────────────────────────────────────────────────

os.makedirs("../logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("../logs/web.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("smtpagent.web")

# ── Minimal EDN → dict reader (covers our meta/config.edn subset) ─────────────

def _edn_str_val(s: str):
    """Very targeted EDN value extractor — handles strings, ints, booleans."""
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    if s in ("true", "false"):
        return s == "true"
    try:
        return int(s)
    except ValueError:
        return s

def load_meta_config(path: str) -> dict:
    """Extract key scalars from meta/config.edn without a full EDN library."""
    try:
        raw = open(path).read()
        # Strip comments
        raw = re.sub(r";[^\n]*", "", raw)
        def grab(key):
            m = re.search(rf':{key}\s+"([^"]*)"', raw)
            return m.group(1) if m else None
        def grab_int(key, default):
            m = re.search(rf':{key}\s+(\d+)', raw)
            return int(m.group(1)) if m else default
        return {
            "web_port":      grab_int("port", 8080),
            "web_bind":      grab("bind") or "0.0.0.0",
            "smtp_host":     grab("host") or "smtp.gmail.com",
            "smtp_port":     grab_int("port", 587),
            "smtp_service":  "http://127.0.0.1:8026",
        }
    except Exception as e:
        log.warning("Could not load meta-config: %s — using defaults", e)
        return {"web_port": 8080, "web_bind": "0.0.0.0",
                "smtp_service": "http://127.0.0.1:8026"}

META = load_meta_config("../meta/config.edn")
SMTP_SERVICE = os.environ.get("SMTP_SERVICE_URL", META["smtp_service"])

# ── Flask app ─────────────────────────────────────────────────────────────────

app = Flask(__name__, template_folder="templates")
app.config["SECRET_KEY"] = os.urandom(24)

@app.route("/", methods=["GET"])
def compose():
    """Render the email compose form."""
    smtp_host = META.get("smtp_host", "smtp.gmail.com")
    return render_template("compose.html", smtp_host=smtp_host)

@app.route("/send", methods=["POST"])
def send():
    """Receive form POST, forward JSON to Clojure SMTP service, return result."""
    data = {
        "cmd":     "send",
        "to":      request.form.get("to", "").strip(),
        "from":    request.form.get("from", "").strip(),
        "subject": request.form.get("subject", "").strip(),
        "body":    request.form.get("body", "").strip(),
    }
    log.info("Outbound send request to=%s subject=%s", data["to"], data["subject"])

    if not data["to"] or not data["subject"] or not data["body"]:
        return jsonify({"ok": False, "error": "to, subject, and body are required"}), 400

    try:
        resp = requests.post(
            f"{SMTP_SERVICE}/send",
            json=data,
            timeout=15,
        )
        result = resp.json()
        log.info("SMTP service response: %s", result)
        if result.get("ok"):
            return render_template("compose.html",
                                   smtp_host=META.get("smtp_host", ""),
                                   success=True,
                                   to=data["to"])
        return render_template("compose.html",
                               smtp_host=META.get("smtp_host", ""),
                               error=result.get("error", "Unknown error")), 500
    except requests.exceptions.ConnectionError:
        log.error("Clojure SMTP service unreachable at %s", SMTP_SERVICE)
        return render_template("compose.html",
                               smtp_host=META.get("smtp_host", ""),
                               error="SMTP service offline. Start with: make start-clojure"), 503

@app.route("/status", methods=["GET"])
def status():
    """Health + SMTP service status."""
    try:
        r = requests.get(f"{SMTP_SERVICE}/status", timeout=5)
        smtp_status = r.json()
    except Exception:
        smtp_status = {"ok": False, "error": "unreachable"}
    return jsonify({"web": "ok", "smtp_service": smtp_status})

@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"ok": True, "layer": "python-web"})

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("WEB_PORT", META["web_port"]))
    bind = os.environ.get("WEB_BIND", META["web_bind"])
    log.info("Singine smtpAgent web UI starting on %s:%d", bind, port)
    log.info("Forwarding sends to SMTP service: %s", SMTP_SERVICE)
    app.run(host=bind, port=port, debug=False)
