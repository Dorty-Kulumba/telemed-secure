"""Test end-to-end du flux login + MFA contre le serveur local."""
import json
import sqlite3
import urllib.request
from pathlib import Path

import pyotp

BASE = "http://127.0.0.1:8000"
DB_PATH = Path(__file__).resolve().parents[1] / "telemed_secure.db"


def post(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get(path, token):
    req = urllib.request.Request(BASE + path, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


status, data = post("/api/login", {"email": "kabu.patient@example.com", "mot_de_passe": "MotDePasseTest1234"})
print("LOGIN:", status, data.get("message") or data)

challenge = data.get("challenge_token")
if challenge:
    # Récupère le secret MFA du compte créé plus tôt
    con = sqlite3.connect(DB_PATH)
    secret = con.execute(
        "select secret_mfa from utilisateurs where email=?", ("kabu.patient@example.com",)
    ).fetchone()[0]
    code = pyotp.TOTP(secret).now()
    status, data = post("/api/mfa/verify", {"challenge_token": challenge, "code_totp": code})
    print("MFA VERIFY:", status, list(data.keys()))
    token = data.get("access_token")
    if token:
        status, me = get("/api/me", token)
        print("GET /api/me:", status, {k: me[k] for k in ("email", "role", "codes_de_secours_restants")})
