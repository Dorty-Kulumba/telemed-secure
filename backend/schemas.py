from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserCreate(InputModel):
    nom: str = Field(min_length=1, max_length=100)
    prenom: str = Field(min_length=1, max_length=100)
    email: EmailStr
    telephone: str | None = Field(default=None, max_length=50)
    mot_de_passe: str = Field(min_length=8, max_length=72)
    role: Literal["Patient"] = "Patient"

    @field_validator("nom", "prenom", "telephone")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Ce champ ne peut pas être vide.")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("mot_de_passe")
    @classmethod
    def limit_bcrypt_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Le mot de passe ne doit pas dépasser 72 octets.")
        return value


class UserLogin(InputModel):
    email: EmailStr
    mot_de_passe: str = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class MFAVerify(InputModel):
    challenge_token: str = Field(min_length=1, max_length=2048)
    code_totp: str = Field(pattern=r"^\d{6}$")


class DossierCreate(InputModel):
    patient_id: int = Field(gt=0)
    contenu: str = Field(min_length=1, max_length=100_000)


class ConsentUpdate(InputModel):
    medecin_id: int = Field(gt=0)
    statut: bool
