"""Create the first administrator after database migrations have been applied."""

from getpass import getpass
from pathlib import Path

from dotenv import load_dotenv
from pydantic import EmailStr, TypeAdapter

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from .database import SessionLocal  # noqa: E402
from .models import JournalAudit, MFARecoveryCode, Utilisateur  # noqa: E402
from .security import (  # noqa: E402
    generate_recovery_codes,
    generate_totp_secret,
    get_totp_provisioning_uri,
    hash_password,
    hash_recovery_code,
)


def main() -> None:
    db = SessionLocal()
    try:
        if db.query(Utilisateur).filter(Utilisateur.role == "Administrateur").first():
            raise SystemExit("Un administrateur existe déjà. Utilisez son interface pour gérer les comptes.")

        nom = input("Nom : ").strip()
        prenom = input("Prénom : ").strip()
        email = TypeAdapter(EmailStr).validate_python(input("Adresse e-mail : ").strip().lower())
        password = getpass("Mot de passe initial (12 caractères minimum) : ")
        confirmation = getpass("Confirmez le mot de passe : ")

        if not nom or not prenom:
            raise SystemExit("Le nom et le prénom sont obligatoires.")
        if password != confirmation:
            raise SystemExit("Les deux mots de passe ne correspondent pas.")
        if len(password) < 12 or len(password.encode("utf-8")) > 72:
            raise SystemExit("Le mot de passe doit faire entre 12 et 72 octets.")

        email = str(email).lower()
        if db.query(Utilisateur).filter(Utilisateur.email == email).first():
            raise SystemExit("Cette adresse e-mail est déjà utilisée.")

        mfa_secret = generate_totp_secret()
        admin = Utilisateur(
            nom=nom,
            prenom=prenom,
            email=email,
            mot_de_passe_hash=hash_password(password),
            role="Administrateur",
            secret_mfa=mfa_secret,
        )
        db.add(admin)
        db.flush()

        recovery_codes = generate_recovery_codes()
        db.add_all(
            MFARecoveryCode(utilisateur_id=admin.id, code_hash=hash_recovery_code(code))
            for code in recovery_codes
        )
        db.add(
            JournalAudit(
                utilisateur_id=admin.id,
                action="ADMIN_INITIAL_CREE",
                ressource="Initialisation locale",
            )
        )
        db.commit()

        print("\nCompte administrateur créé.")
        print(f"Clé MFA : {mfa_secret}")
        print(f"Lien MFA : {get_totp_provisioning_uri(mfa_secret, email)}")
        print("Codes de secours (à conserver une seule fois) :")
        print("\n".join(recovery_codes))
        print("\nEnregistrez ces informations dans un endroit privé.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
