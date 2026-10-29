"""Vérification complète : schéma SQLite, inscription, connexion, MFA."""
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pyotp

BASE = "http://127.0.0.1:8000"
DB = Path(__file__).resolve().parents[1] / "telemed_secure.db"


def call(method, path, payload=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except urllib.error.URLError as e:
        print(f"SERVEUR INJOIGNABLE: {e}")
        sys.exit(1)


print("1) SCHÉMA SQLite")
con = sqlite3.connect(DB)
tables = [r[0] for r in con.execute("select name from sqlite_master where type='table' order by name")]
print("   tables :", ", ".join(tables))

print("\n2) INSCRIPTION")
email = f"verif.{int(time.time())}@example.com"
mot_de_passe = "MotDePasseTest1234"
status, data = call(
    "POST",
    "/api/register",
    {"nom": "Vérif", "prenom": "Auto", "email": email, "mot_de_passe": mot_de_passe},
)
print(f"   POST /api/register -> {status}")
if status != 201:
    print("   détail :", data)
    sys.exit(1)
print("   secret MFA :", data["mfa"]["secret"])
print("   codes de secours :", len(data["codes_de_secours"]))

print("\n3) CONNEXION + MFA")
status, login = call("POST", "/api/login", {"email": email, "mot_de_passe": mot_de_passe})
print(f"   POST /api/login -> {status}")
code = pyotp.TOTP(data["mfa"]["secret"]).now()
status, mfa = call(
    "POST", "/api/mfa/verify", {"challenge_token": login["challenge_token"], "code_totp": code}
)
print(f"   POST /api/mfa/verify (code {code}) -> {status}")

print("\n4) SESSION")
status, me = call("GET", "/api/me", token=mfa["access_token"])
print(f"   GET /api/me -> {status}  {(me.get('prenom'), me.get('nom'), me.get('role'))}")
print(f"   codes de secours restants : {me.get('codes_de_secours_restants')}")

print("\n5) CONTRÔLE DE LA LIGNE EN BASE")
row = con.execute(
    "select email, role, length(mot_de_passe_hash), mot_de_passe_a_changer, token_version "
    "from utilisateurs where email=?",
    (email,),
).fetchone()
print("   ", row)
print("   hash bcrypt :", row[2] == 60)
