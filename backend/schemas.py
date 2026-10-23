from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    nom: str
    prenom: str
    email: EmailStr
    telephone: str | None = None
    mot_de_passe: str
    role: str  # Patient, Médecin, Administrateur

class UserLogin(BaseModel):
    email: EmailStr
    mot_de_passe: str

class MFAVerify(BaseModel):
    email: EmailStr
    code_totp: str

class DossierCreate(BaseModel):
    patient_id: int
    contenu: str

class ConsentUpdate(BaseModel):
    medecin_id: int
    statut: bool