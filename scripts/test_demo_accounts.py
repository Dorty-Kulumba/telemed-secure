"""Vérifie que les 3 comptes de démonstration se connectent sans SMTP."""
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


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


status, accounts = call("GET", "/api/dev/test-accounts")
print(f"comptes de démo : HTTP {status} ({len(accounts)} comptes)\n")

for account in accounts:
    s1, login = call(
        "POST",
        "/api/login",
        {"email": account["email"], "mot_de_passe": account["mot_de_passe"]},
    )
    if s1 != 200:
        print(f"[KO] {account['email']} login -> {s1} {login}")
        continue

    s2, mfa = call(
        "POST",
        "/api/mfa/verify",
        {"challenge_token": login["challenge_token"], "code_totp": account["code_totp"]},
    )
    if s2 != 200:
        print(f"[KO] {account['email']} mfa -> {s2} {mfa}")
        continue

    s3, me = call("GET", "/api/me", token=mfa["access_token"])
    print(
        f"[OK] {account['email']:<28} role={me['role']:<15} "
        f"login={s1} mfa={s2} me={s3} codes_secours={me['codes_de_secours_restants']}"
    )
