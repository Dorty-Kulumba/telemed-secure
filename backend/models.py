from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.sql import func
from .database import Base

class Utilisateur(Base):
    __tablename__ = "utilisateurs"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    telephone = Column(String(50), nullable=True)
    mot_de_passe_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # Patient, Médecin, Administrateur
    secret_mfa = Column(String(100), nullable=True)
    actif = Column(Boolean, default=True)
    date_creation = Column(DateTime(timezone=True), server_default=func.now())

class DossierMedical(Base):
    __tablename__ = "dossiers_medicaux"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("utilisateurs.id"), nullable=False)
    contenu_chiffre = Column(Text, nullable=False)  # Chiffré en AES-GCM
    date_creation = Column(DateTime(timezone=True), server_default=func.now())

class Consentement(Base):
    __tablename__ = "consentements"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("utilisateurs.id"), nullable=False)
    medecin_id = Column(Integer, ForeignKey("utilisateurs.id"), nullable=False)
    statut = Column(Boolean, default=False)  # True = consenti, False = révoqué
    date_creation = Column(DateTime(timezone=True), server_default=func.now())
    date_modification = Column(DateTime(timezone=True), onupdate=func.now())

class JournalAudit(Base):
    __tablename__ = "journal_audit"

    id = Column(Integer, primary_key=True, index=True)
    utilisateur_id = Column(Integer, ForeignKey("utilisateurs.id"), nullable=True)
    action = Column(String(255), nullable=False)
    ressource = Column(String(255), nullable=False)
    adresse_ip = Column(String(50), nullable=True)
    date_creation = Column(DateTime(timezone=True), server_default=func.now())
