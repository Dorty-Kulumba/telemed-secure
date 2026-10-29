import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from .database import Base, engine, get_db  # noqa: E402
from .models import Consentement, DossierMedical, JournalAudit, Utilisateur  # noqa: E402
from .schemas import ConsentUpdate, DossierCreate, MFAVerify, UserCreate, UserLogin  # noqa: E402
from .security import (  # noqa: E402
    create_access_token,
    create_mfa_challenge_token,
    encrypt_medical_record,
    generate_totp_secret,
    get_totp_provisioning_uri,
    hash_password,
    verify_access_token,
    verify_mfa_challenge_token,
    verify_password,
    verify_totp_code,
)

app = FastAPI(title="Telemed Secure API", version="1.1.0")
security = HTTPBearer()

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Authorization", "Content-Type"],
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Utilisateur:
    payload = verify_access_token(credentials.credentials)
    user_id = payload.get("id") if payload else None
    if not isinstance(user_id, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalide ou expirée.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(Utilisateur, user_id)
    if not user or not user.actif:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte introuvable ou désactivé.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(user: Utilisateur, *allowed_roles: str) -> None:
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas l'autorisation d'effectuer cette action.",
        )


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/register", status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    email = str(user_data.email).strip().lower()
    if db.query(Utilisateur).filter(Utilisateur.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet e-mail est déjà utilisé.")

    mfa_secret = generate_totp_secret()
    new_user = Utilisateur(
        nom=user_data.nom,
        prenom=user_data.prenom,
        email=email,
        telephone=user_data.telephone,
        mot_de_passe_hash=hash_password(user_data.mot_de_passe),
        role="Patient",
        secret_mfa=mfa_secret,
    )

    try:
        db.add(new_user)
        db.flush()
        db.add(
            JournalAudit(
                utilisateur_id=new_user.id,
                action="CREATION_COMPTE",
                ressource="Compte utilisateur",
                adresse_ip=request.client.host if request.client else None,
            )
        )
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet e-mail est déjà utilisé.")
    except Exception:
        db.rollback()
        raise

    return {
        "message": "Compte créé. Configurez votre application d'authentification avant de vous connecter.",
        "mfa": {
            "secret": mfa_secret,
            "provisioning_uri": get_totp_provisioning_uri(mfa_secret, email),
        },
    }


@app.post("/api/login")
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    email = str(credentials.email).strip().lower()
    user = db.query(Utilisateur).filter(Utilisateur.email == email).first()
    if not user or not user.actif or not verify_password(
        credentials.mot_de_passe, user.mot_de_passe_hash
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants incorrects.")

    if not user.secret_mfa:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La vérification MFA n'est pas configurée pour ce compte.",
        )

    return {
        "message": "Identifiants valides. Saisissez le code de votre application d'authentification.",
        "challenge_token": create_mfa_challenge_token({"sub": user.email, "id": user.id}),
    }


@app.post("/api/mfa/verify")
def verify_mfa(data: MFAVerify, db: Session = Depends(get_db)):
    challenge = verify_mfa_challenge_token(data.challenge_token)
    user_id = challenge.get("id") if challenge else None
    if not isinstance(user_id, int):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Demande MFA invalide ou expirée.")

    user = db.get(Utilisateur, user_id)
    if not user or not user.actif or not user.secret_mfa:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Compte introuvable ou désactivé.")
    if not verify_totp_code(user.secret_mfa, data.code_totp):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Code MFA/TOTP invalide.")

    token = create_access_token({"sub": user.email, "role": user.role, "id": user.id})
    db.add(
        JournalAudit(
            utilisateur_id=user.id,
            action="CONNEXION_MFA_REUSSIE",
            ressource="Module d'authentification",
        )
    )
    db.commit()
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/me")
def get_profile(user: Utilisateur = Depends(get_current_user)):
    return {
        "id": user.id,
        "nom": user.nom,
        "prenom": user.prenom,
        "email": user.email,
        "role": user.role,
    }


@app.put("/api/consentements")
def update_consent(
    data: ConsentUpdate,
    request: Request,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, "Patient")
    doctor = db.get(Utilisateur, data.medecin_id)
    if not doctor or doctor.role not in {"Médecin", "Spécialiste"} or not doctor.actif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Praticien introuvable.")

    consent = (
        db.query(Consentement)
        .filter(
            Consentement.patient_id == user.id,
            Consentement.medecin_id == data.medecin_id,
        )
        .first()
    )
    if consent:
        consent.statut = data.statut
    else:
        consent = Consentement(
            patient_id=user.id,
            medecin_id=data.medecin_id,
            statut=data.statut,
        )
        db.add(consent)

    db.add(
        JournalAudit(
            utilisateur_id=user.id,
            action="CONSENTEMENT_MODIFIE",
            ressource=f"Accès du praticien {doctor.id}",
            adresse_ip=request.client.host if request.client else None,
        )
    )
    db.commit()
    return {"message": "Consentement mis à jour.", "statut": consent.statut}


@app.post("/api/dossiers", status_code=status.HTTP_201_CREATED)
def create_dossier(
    dossier: DossierCreate,
    request: Request,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, "Médecin", "Spécialiste")
    patient = db.get(Utilisateur, dossier.patient_id)
    if not patient or patient.role != "Patient" or not patient.actif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable.")

    consent = (
        db.query(Consentement)
        .filter(
            Consentement.patient_id == patient.id,
            Consentement.medecin_id == user.id,
            Consentement.statut.is_(True),
        )
        .first()
    )
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Le patient n'a pas accordé son consentement à ce praticien.",
        )

    db.add(
        DossierMedical(
            patient_id=patient.id,
            contenu_chiffre=encrypt_medical_record(dossier.contenu),
        )
    )
    db.add(
        JournalAudit(
            utilisateur_id=user.id,
            action="CREATION_DOSSIER_MEDICAL",
            ressource=f"Dossier patient {patient.id}",
            adresse_ip=request.client.host if request.client else None,
        )
    )
    db.commit()
    return {"message": "Dossier médical chiffré et enregistré avec succès."}


@app.get("/api/audit")
def get_audit_logs(
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, "Administrateur")
    logs = (
        db.query(JournalAudit)
        .order_by(JournalAudit.date_creation.desc(), JournalAudit.id.desc())
        .limit(500)
        .all()
    )
    return [
        {
            "id": log.id,
            "utilisateur_id": log.utilisateur_id,
            "action": log.action,
            "ressource": log.ressource,
            "adresse_ip": log.adresse_ip,
            "date_creation": log.date_creation,
        }
        for log in logs
    ]


# La racine doit être montée après les routes API pour que celles-ci restent accessibles.
frontend_path = Path(__file__).resolve().parents[1] / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")

Base.metadata.create_all(bind=engine)
