"""Outils de démonstration locale — montés uniquement si ENABLE_TEST_ACCOUNTS=true.

Aucun e-mail n'est envoyé : les codes MFA sont calculés à la volée et exposés
dans l'interface de test, puisque ce projet local n'a pas de serveur SMTP.
Ce module ne doit jamais être activé en production.
"""

import time

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import JournalAudit, MFARecoveryCode, Utilisateur
from .security import (
    generate_recovery_codes,
    generate_totp_secret,
    get_totp_provisioning_uri,
    hash_password,
    hash_recovery_code,
)

router = APIRouter(prefix="/api/dev", tags=["demonstration"])

# Comptes de test créés à la demande. Les mots de passe sont volontairement
# simples et connus : ils ne servent qu'en local.
TEST_ACCOUNTS = (
    {
        "role": "Patient",
        "nom": "Patient",
        "prenom": "Démo",
        "email": "demo.patient@example.com",
        "mot_de_passe": "DemoPatient2026!",
        "telephone": "+242060000001",
    },
    {
        "role": "Médecin",
        "nom": "Médecin",
        "prenom": "Démo",
        "email": "demo.medecin@example.com",
        "mot_de_passe": "DemoMedecin2026!",
        "telephone": "+242060000002",
    },
    {
        "role": "Administrateur",
        "nom": "Admin",
        "prenom": "Démo",
        "email": "demo.admin@example.com",
        "mot_de_passe": "DemoAdmin2026!",
        "telephone": "+242060000003",
    },
)


def _create_demo_user(db: Session, spec: dict) -> Utilisateur:
    user = Utilisateur(
        nom=spec["nom"],
        prenom=spec["prenom"],
        email=spec["email"],
        telephone=spec["telephone"],
        mot_de_passe_hash=hash_password(spec["mot_de_passe"]),
        role=spec["role"],
        secret_mfa=generate_totp_secret(),
        actif=True,
    )
    db.add(user)
    db.flush()
    db.add_all(
        MFARecoveryCode(utilisateur_id=user.id, code_hash=hash_recovery_code(code))
        for code in generate_recovery_codes()
    )
    db.add(
        JournalAudit(
            utilisateur_id=user.id,
            action="COMPTE_DEMONSTRATION_CREE",
            ressource=f"Compte {spec['role']}",
        )
    )
    return user


def _ensure_demo_users(db: Session) -> None:
    created = False
    for spec in TEST_ACCOUNTS:
        existing = db.query(Utilisateur).filter(Utilisateur.email == spec["email"]).first()
        if existing is None:
            _create_demo_user(db, spec)
            created = True
    if created:
        db.commit()


def _account_payload(user: Utilisateur, spec: dict) -> dict:
    totp = pyotp.TOTP(user.secret_mfa)
    expires_in = totp.interval - (int(time.time()) % totp.interval)
    return {
        "role": user.role,
        "nom": user.nom,
        "prenom": user.prenom,
        "email": user.email,
        "mot_de_passe": spec["mot_de_passe"],
        "secret_mfa": user.secret_mfa,
        "provisioning_uri": get_totp_provisioning_uri(user.secret_mfa, user.email),
        "code_totp": totp.now(),
        "expire_dans": expires_in,
    }


@router.post("/seed", status_code=status.HTTP_201_CREATED)
def seed_demo_accounts(request: Request, db: Session = Depends(get_db)):
    """Crée les comptes de démonstration s'ils n'existent pas (idempotent)."""
    _ensure_demo_users(db)
    return {
        "message": "Comptes de démonstration prêts. Aucun e-mail n'est envoyé.",
        "comptes": [
            {k: v for k, v in _account_payload(
                db.query(Utilisateur).filter(Utilisateur.email == spec["email"]).one(), spec
            ).items() if k in {"role", "email", "mot_de_passe"}}
            for spec in TEST_ACCOUNTS
        ],
    }


@router.get("/test-accounts")
def list_demo_accounts(db: Session = Depends(get_db)):
    """Renvoie les comptes de démo et le code TOTP courant (mode simulation)."""
    _ensure_demo_users(db)
    payload = []
    for spec in TEST_ACCOUNTS:
        user = db.query(Utilisateur).filter(Utilisateur.email == spec["email"]).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Compte de démonstration introuvable.",
            )
        account = _account_payload(user, spec)
        account["codes_de_secours_restants"] = (
            db.query(MFARecoveryCode)
            .filter(
                MFARecoveryCode.utilisateur_id == user.id,
                MFARecoveryCode.utilise_le.is_(None),
            )
            .count()
        )
        payload.append(account)
    return payload
