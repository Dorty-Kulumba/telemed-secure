import os
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

# Vérification critique des variables d'environnement (Règle de sécurité du projet)
SECRET_KEY = os.getenv("SECRET_KEY")
TOTP_SECRET = os.getenv("TOTP_SECRET")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY absente du fichier .env")
if not TOTP_SECRET:
    raise RuntimeError("TOTP_SECRET absente du fichier .env")

from database import engine, Base, get_db
from models import Utilisateur, DossierMedical, Consentement, JournalAudit
from schemas import UserCreate, UserLogin, MFAVerify, DossierCreate, ConsentUpdate
from security import (
    hash_password, verify_password, create_access_token,
    verify_access_token, verify_totp_code, generate_totp_secret,
    encrypt_medical_record, decrypt_medical_record
)

# Configuration du schéma de sécurité HTTP Bearer pour Swagger UI
security = HTTPBearer()

# Création automatique des tables dans PostgreSQL au démarrage
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Telemed Secure API", version="1.0.0")

# Configuration CORS pour autoriser le frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Intégration et service direct du dossier Frontend à la racine pour charger index.html, CSS et JS
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")

if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

# 1. Inscription d'un utilisateur
@app.post("/api/register")
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(Utilisateur).filter(Utilisateur.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Cet e-mail est déjà utilisé.")
    
    hashed_pwd = hash_password(user_data.mot_de_passe)
    mfa_sec = generate_totp_secret() if user_data.role in ["Patient", "Médecin"] else None

    new_user = Utilisateur(
        nom=user_data.nom,
        prenom=user_data.prenom,
        email=user_data.email,
        telephone=user_data.telephone,
        mot_de_passe_hash=hashed_pwd,
        role=user_data.role,
        secret_mfa=mfa_sec
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "Utilisateur créé avec succès", "mfa_secret_genere": mfa_sec}

# 2. Étape 1 de Connexion (Vérification des identifiants et déclenchement du challenge MFA)
@app.post("/api/login")
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(Utilisateur).filter(Utilisateur.email == credentials.email).first()
    if not user or not verify_password(credentials.mot_de_passe, user.mot_de_passe_hash):
        raise HTTPException(status_code=401, detail="Identifiants incorrects.")
    
    return {"message": "Identifiants valides. Veuillez soumettre le code MFA/TOTP.", "email": user.email}

# 3. Étape 2 de Connexion (Validation du code TOTP et génération du Jeton JWT)
@app.post("/api/mfa/verify")
def verify_mfa(data: MFAVerify, db: Session = Depends(get_db)):
    user = db.query(Utilisateur).filter(Utilisateur.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    
    # Si l'utilisateur n'a pas de secret MFA, on utilise le secret global de secours du .env
    secret_to_use = user.secret_mfa if user.secret_mfa else TOTP_SECRET
    
    if not verify_totp_code(secret_to_use, data.code_totp):
        raise HTTPException(status_code=401, detail="Code MFA/TOTP invalide.")
    
    # Génération du jeton JWT sécurisé
    token = create_access_token({"sub": user.email, "role": user.role, "id": user.id})
    
    # Journalisation de l'action dans la table d'audit
    audit = JournalAudit(utilisateur_id=user.id, action="CONNEXION_MFA_REUSSIE", ressource="Auth Module")
    db.add(audit)
    db.commit()

    return {"access_token": token, "token_type": "bearer", "role": user.role, "nom": user.nom}

# 4. Création d'un dossier médical chiffré (AES-GCM) - Sécurisé par HTTP Bearer
@app.post("/api/dossiers")
def create_dossier(dossier: DossierCreate, request: Request, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton JWT invalide ou expiré.")

    # Chiffrement symétrique fort AES-GCM
    contenu_chiffre = encrypt_medical_record(dossier.contenu)
    
    nouveau_dossier = DossierMedical(
        patient_id=dossier.patient_id,
        contenu_chiffre=contenu_chiffre
    )
    db.add(nouveau_dossier)
    
    # Ajout dans le journal d'audit
    audit = JournalAudit(
        action="CREATION_DOSSIER_MEDICAL",
        ressource=f"Dossier Patient ID {dossier.patient_id}",
        adresse_ip=request.client.host if request.client else "Inconnue"
    )
    db.add(audit)
    db.commit()
    
    return {"message": "Dossier médical chiffré et enregistré avec succès (AES-GCM)."}

# 5. Consultation des journaux d'audit (Réservé à l'Administrateur)
@app.get("/api/audit")
def get_audit_logs(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton JWT invalide ou expiré.")
    
    logs = db.query(JournalAudit).all()
    return logs

# --- PLACEZ LE MOUNT DU FRONTEND TOUT À LA FIN ---
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")

if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")