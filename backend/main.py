import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from .database import get_db  # noqa: E402
from .models import (  # noqa: E402
    Consentement,
    DossierMedical,
    JournalAudit,
    MFARecoveryCode,
    Utilisateur,
)
from .schemas import (  # noqa: E402
    AdminUserCreate,
    ConsentUpdate,
    DossierCreate,
    MFAVerify,
    PasswordUpdate,
    UserCreate,
    UserLogin,
    UserStatusUpdate,
)
from .security import (  # noqa: E402
    create_access_token,
    create_mfa_challenge_token,
    decrypt_medical_record,
    encrypt_medical_record,
    generate_recovery_codes,
    generate_totp_secret,
    get_totp_provisioning_uri,
    hash_password,
    hash_recovery_code,
    verify_access_token,
    verify_mfa_challenge_token,
    verify_password,
    verify_totp_code,
)

app = FastAPI(title="Telemed Secure API", version="1.2.0")
security = HTTPBearer()
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("RATE_LIMIT_STORAGE_URI", "memory://"),
    headers_enabled=True,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )


def _audit(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    resource: str,
    request: Request | None = None,
) -> None:
    db.add(
        JournalAudit(
            utilisateur_id=user_id,
            action=action,
            ressource=resource,
            adresse_ip=request.client.host if request and request.client else None,
        )
    )


def _replace_recovery_codes(db: Session, user_id: int) -> list[str]:
    codes = generate_recovery_codes()
    db.query(MFARecoveryCode).filter(MFARecoveryCode.utilisateur_id == user_id).delete(
        synchronize_session=False
    )
    db.add_all(
        MFARecoveryCode(utilisateur_id=user_id, code_hash=hash_recovery_code(code))
        for code in codes
    )
    return codes


def get_current_user(
    request: Request,
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
    if not user or not user.actif or payload.get("ver") != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte introuvable ou désactivé.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.mot_de_passe_a_changer and request.url.path not in {
        "/api/me",
        "/api/account/password",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Changez votre mot de passe temporaire avant de continuer.",
        )
    return user


def require_role(user: Utilisateur, *allowed_roles: str) -> None:
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas l'autorisation d'effectuer cette action.",
        )


def _access_token_for(user: Utilisateur) -> str:
    return create_access_token(
        {"sub": user.email, "role": user.role, "id": user.id, "ver": user.token_version}
    )


def _user_summary(user: Utilisateur) -> dict:
    return {
        "id": user.id,
        "nom": user.nom,
        "prenom": user.prenom,
        "email": user.email,
        "telephone": user.telephone,
        "role": user.role,
        "actif": user.actif,
        "mot_de_passe_a_changer": user.mot_de_passe_a_changer,
        "date_creation": user.date_creation,
    }


def _record_result(record: DossierMedical) -> dict:
    try:
        content = decrypt_medical_record(record.contenu_chiffre)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Le dossier ne peut pas être déchiffré avec la clé configurée.",
        ) from exc
    return {"id": record.id, "contenu": content, "date_creation": record.date_creation}


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
def register(
    request: Request,
    response: Response,
    user_data: UserCreate,
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
        recovery_codes = _replace_recovery_codes(db, new_user.id)
        _audit(db, user_id=new_user.id, action="CREATION_COMPTE", resource="Compte Patient", request=request)
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet e-mail est déjà utilisé.")
    except Exception:
        db.rollback()
        raise

    return {
        "message": "Compte créé. Configurez votre application MFA et conservez vos codes de secours.",
        "mfa": {
            "secret": mfa_secret,
            "provisioning_uri": get_totp_provisioning_uri(mfa_secret, email),
        },
        "codes_de_secours": recovery_codes,
    }


@app.post("/api/login")
@limiter.limit("10/minute")
def login(request: Request, response: Response, credentials: UserLogin, db: Session = Depends(get_db)):
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
        "message": "Identifiants valides. Saisissez votre code MFA ou un code de secours.",
        "challenge_token": create_mfa_challenge_token(
            {"sub": user.email, "id": user.id, "ver": user.token_version}
        ),
    }


@app.post("/api/mfa/verify")
@limiter.limit("10/minute")
def verify_mfa(request: Request, response: Response, data: MFAVerify, db: Session = Depends(get_db)):
    challenge = verify_mfa_challenge_token(data.challenge_token)
    user_id = challenge.get("id") if challenge else None
    if not isinstance(user_id, int):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Demande MFA invalide ou expirée.")

    user = db.get(Utilisateur, user_id)
    if not user or not user.actif or not user.secret_mfa or challenge.get("ver") != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Compte introuvable ou désactivé.")

    if data.code_totp:
        if not verify_totp_code(user.secret_mfa, data.code_totp):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Code MFA/TOTP invalide.")
        auth_method = "TOTP"
    else:
        recovery_hash = hash_recovery_code(data.recovery_code or "")
        consumed = (
            db.query(MFARecoveryCode)
            .filter(
                MFARecoveryCode.utilisateur_id == user.id,
                MFARecoveryCode.code_hash == recovery_hash,
                MFARecoveryCode.utilise_le.is_(None),
            )
            .update({MFARecoveryCode.utilise_le: func.now()}, synchronize_session=False)
        )
        if consumed != 1:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Code de secours invalide ou déjà utilisé.")
        auth_method = "CODE_SECOURS"

    token = _access_token_for(user)
    _audit(
        db,
        user_id=user.id,
        action="CONNEXION_MFA_REUSSIE",
        resource=f"Authentification {auth_method}",
        request=request,
    )
    db.commit()
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/me")
def get_profile(
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    remaining_codes = (
        db.query(MFARecoveryCode)
        .filter(
            MFARecoveryCode.utilisateur_id == user.id,
            MFARecoveryCode.utilise_le.is_(None),
        )
        .count()
    )
    return {
        **_user_summary(user),
        "codes_de_secours_restants": remaining_codes,
    }


@app.put("/api/account/password")
def change_password(
    data: PasswordUpdate,
    request: Request,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.mot_de_passe_actuel, user.mot_de_passe_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le mot de passe actuel est incorrect.")
    if data.mot_de_passe_actuel == data.nouveau_mot_de_passe:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choisissez un nouveau mot de passe différent.")
    user.mot_de_passe_hash = hash_password(data.nouveau_mot_de_passe)
    user.mot_de_passe_a_changer = False
    user.token_version += 1
    _audit(db, user_id=user.id, action="MOT_DE_PASSE_MODIFIE", resource="Compte utilisateur", request=request)
    db.commit()
    return {"message": "Mot de passe mis à jour.", "access_token": _access_token_for(user)}


@app.post("/api/mfa/recovery-codes")
def rotate_recovery_codes(
    request: Request,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    codes = _replace_recovery_codes(db, user.id)
    _audit(db, user_id=user.id, action="CODES_SECOURS_REGENEREES", resource="MFA", request=request)
    db.commit()
    return {
        "message": "Ces codes ne seront plus affichés. Conservez-les dans un endroit sûr.",
        "codes_de_secours": codes,
    }


@app.get("/api/praticiens")
def list_practitioners(
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, "Patient")
    practitioners = (
        db.query(Utilisateur)
        .filter(Utilisateur.role.in_(["Médecin", "Spécialiste"]), Utilisateur.actif.is_(True))
        .order_by(Utilisateur.nom, Utilisateur.prenom)
        .all()
    )
    return [{"id": person.id, "nom": person.nom, "prenom": person.prenom} for person in practitioners]


@app.get("/api/consentements")
def list_patient_consents(
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, "Patient")
    consents = (
        db.query(Consentement, Utilisateur)
        .join(Utilisateur, Utilisateur.id == Consentement.medecin_id)
        .filter(Consentement.patient_id == user.id)
        .order_by(Utilisateur.nom, Utilisateur.prenom)
        .all()
    )
    return [
        {
            "medecin_id": consent.medecin_id,
            "medecin": f"{doctor.prenom} {doctor.nom}",
            "statut": consent.statut,
        }
        for consent, doctor in consents
    ]


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
        consent = Consentement(patient_id=user.id, medecin_id=data.medecin_id, statut=data.statut)
        db.add(consent)
    _audit(
        db,
        user_id=user.id,
        action="CONSENTEMENT_MODIFIE",
        resource=f"Accès du praticien {doctor.id}",
        request=request,
    )
    db.commit()
    return {"message": "Consentement mis à jour.", "statut": consent.statut}


@app.get("/api/dossiers/moi")
def list_my_records(
    request: Request,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, "Patient")
    records = (
        db.query(DossierMedical)
        .filter(DossierMedical.patient_id == user.id)
        .order_by(DossierMedical.date_creation.desc(), DossierMedical.id.desc())
        .all()
    )
    _audit(db, user_id=user.id, action="CONSULTATION_DOSSIERS", resource="Dossier médical personnel", request=request)
    db.commit()
    return [_record_result(record) for record in records]


@app.get("/api/patients-consentis")
def list_consented_patients(
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, "Médecin", "Spécialiste")
    patients = (
        db.query(Utilisateur)
        .join(Consentement, Consentement.patient_id == Utilisateur.id)
        .filter(
            Consentement.medecin_id == user.id,
            Consentement.statut.is_(True),
            Utilisateur.role == "Patient",
            Utilisateur.actif.is_(True),
        )
        .order_by(Utilisateur.nom, Utilisateur.prenom)
        .all()
    )
    return [{"id": patient.id, "nom": patient.nom, "prenom": patient.prenom} for patient in patients]


@app.get("/api/patients/{patient_id}/dossiers")
def list_patient_records_for_doctor(
    patient_id: int,
    request: Request,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, "Médecin", "Spécialiste")
    patient = db.get(Utilisateur, patient_id)
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Le patient n'a pas accordé son consentement.")

    records = (
        db.query(DossierMedical)
        .filter(DossierMedical.patient_id == patient.id)
        .order_by(DossierMedical.date_creation.desc(), DossierMedical.id.desc())
        .all()
    )
    _audit(
        db,
        user_id=user.id,
        action="CONSULTATION_DOSSIERS_PATIENT",
        resource=f"Dossier patient {patient.id}",
        request=request,
    )
    db.commit()
    return [_record_result(record) for record in records]


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

    db.add(DossierMedical(patient_id=patient.id, contenu_chiffre=encrypt_medical_record(dossier.contenu)))
    _audit(
        db,
        user_id=user.id,
        action="CREATION_DOSSIER_MEDICAL",
        resource=f"Dossier patient {patient.id}",
        request=request,
    )
    db.commit()
    return {"message": "Dossier médical chiffré et enregistré avec succès."}


@app.get("/api/admin/users")
def list_users(
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, "Administrateur")
    users = db.query(Utilisateur).order_by(Utilisateur.date_creation.desc(), Utilisateur.id.desc()).limit(500).all()
    return [_user_summary(person) for person in users]


@app.post("/api/admin/users", status_code=status.HTTP_201_CREATED)
def create_managed_user(
    user_data: AdminUserCreate,
    request: Request,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, "Administrateur")
    email = str(user_data.email).strip().lower()
    if db.query(Utilisateur).filter(Utilisateur.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet e-mail est déjà utilisé.")

    temporary_password = secrets.token_urlsafe(24)
    mfa_secret = generate_totp_secret()
    new_user = Utilisateur(
        nom=user_data.nom,
        prenom=user_data.prenom,
        email=email,
        telephone=user_data.telephone,
        mot_de_passe_hash=hash_password(temporary_password),
        role=user_data.role,
        secret_mfa=mfa_secret,
        mot_de_passe_a_changer=True,
    )
    try:
        db.add(new_user)
        db.flush()
        recovery_codes = _replace_recovery_codes(db, new_user.id)
        _audit(db, user_id=user.id, action="COMPTE_PRIVILEGIE_CREE", resource=f"Compte {new_user.role} {new_user.id}", request=request)
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet e-mail est déjà utilisé.")
    except Exception:
        db.rollback()
        raise

    return {
        "compte": _user_summary(new_user),
        "mot_de_passe_temporaire": temporary_password,
        "mfa": {
            "secret": mfa_secret,
            "provisioning_uri": get_totp_provisioning_uri(mfa_secret, email),
        },
        "codes_de_secours": recovery_codes,
    }


@app.post("/api/admin/users/{user_id}/reset-access")
def reset_user_access(
    user_id: int,
    request: Request,
    admin: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(admin, "Administrateur")
    target = db.get(Utilisateur, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compte introuvable.")

    temporary_password = secrets.token_urlsafe(24)
    mfa_secret = generate_totp_secret()
    target.mot_de_passe_hash = hash_password(temporary_password)
    target.secret_mfa = mfa_secret
    target.mot_de_passe_a_changer = True
    target.token_version += 1
    recovery_codes = _replace_recovery_codes(db, target.id)
    _audit(
        db,
        user_id=admin.id,
        action="ACCES_COMPTE_REINITIALISE",
        resource=f"Compte utilisateur {target.id}",
        request=request,
    )
    db.commit()
    return {
        "message": "Transmettez ces données au titulaire par un canal privé. Elles ne seront plus affichées.",
        "compte": _user_summary(target),
        "mot_de_passe_temporaire": temporary_password,
        "mfa": {
            "secret": mfa_secret,
            "provisioning_uri": get_totp_provisioning_uri(mfa_secret, target.email),
        },
        "codes_de_secours": recovery_codes,
    }


@app.patch("/api/admin/users/{user_id}/status")
def update_user_status(
    user_id: int,
    data: UserStatusUpdate,
    request: Request,
    admin: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(admin, "Administrateur")
    target = db.get(Utilisateur, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compte introuvable.")
    if target.id == admin.id and not data.actif:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vous ne pouvez pas désactiver votre propre compte.")
    if target.role == "Administrateur" and target.actif and not data.actif:
        active_admins = (
            db.query(Utilisateur)
            .filter(Utilisateur.role == "Administrateur", Utilisateur.actif.is_(True))
            .count()
        )
        if active_admins <= 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conservez au moins un administrateur actif.")

    if target.actif != data.actif:
        target.token_version += 1
    target.actif = data.actif
    _audit(
        db,
        user_id=admin.id,
        action="COMPTE_ACTIVE" if data.actif else "COMPTE_DESACTIVE",
        resource=f"Compte utilisateur {target.id}",
        request=request,
    )
    db.commit()
    return {"message": "Statut du compte mis à jour.", "compte": _user_summary(target)}


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


# Le frontend est monté en dernier pour que les routes API restent prioritaires.
frontend_path = Path(__file__).resolve().parents[1] / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")

