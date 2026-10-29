"""Bascule .env sur SQLite pour les tests locaux, en conservant l'URL Postgres en commentaire."""
from pathlib import Path

env_path = Path(__file__).resolve().parent / ".env"
lines = env_path.read_text(encoding="utf-8").splitlines()

out = []
switched = False
for line in lines:
    if line.startswith("DATABASE_URL="):
        if not switched:
            pg = line[len("DATABASE_URL="):]
            out.append("# URL PostgreSQL d'origine (conservée pour plus tard, non utilisée en local) :")
            out.append(f"# DATABASE_URL={pg}")
            out.append("# Base SQLite locale pour les tests")
            out.append("DATABASE_URL=sqlite:///./telemed_secure.db")
            switched = True
        continue
    out.append(line)

if not switched:
    out.append("DATABASE_URL=sqlite:///./telemed_secure.db")

env_path.write_text("\n".join(out) + "\n", encoding="utf-8")

# Vérification sans divulguer de secret
for line in env_path.read_text(encoding="utf-8").splitlines():
    if line.startswith("DATABASE_URL="):
        print("ACTIF  ->", line)
    elif line.startswith("# DATABASE_URL="):
        print("COMMENTE ->", line.split("@")[-1])
