import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import pyotp
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY.encode("utf-8")) < 32:
    raise RuntimeError("SECRET_KEY doit être définie et contenir au moins 32 octets.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
MFA_CHALLENGE_EXPIRE_MINUTES = 5


def _load_aes_key() -> bytes:
    configured_key = os.getenv("AES_ENCRYPTION_KEY")
    if configured_key:
        try:
            key = base64.b64decode(configured_key, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise RuntimeError("AES_ENCRYPTION_KEY doit être une clé AES-256 encodée en base64.") from exc
        if len(key) != 32:
            raise RuntimeError("AES_ENCRYPTION_KEY doit décoder exactement 32 octets.")
        return key

    # Clé stable en développement; en production, définir une clé AES dédiée.
    return hmac.new(
        SECRET_KEY.encode("utf-8"),
        b"telemed-secure-medical-records-aes-256-gcm-v1",
        hashlib.sha256,
    ).digest()


AES_KEY = _load_aes_key()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(data: dict, expires_delta: timedelta, token_type: str) -> str:
    payload = data.copy()
    payload["token_type"] = token_type
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    return _create_token(
        data,
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "access",
    )


def create_mfa_challenge_token(data: dict) -> str:
    return _create_token(data, timedelta(minutes=MFA_CHALLENGE_EXPIRE_MINUTES), "mfa_challenge")


def _decode_token(token: str, expected_type: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("token_type") != expected_type:
        return None
    return payload


def verify_access_token(token: str) -> dict | None:
    return _decode_token(token, "access")


def verify_mfa_challenge_token(token: str) -> dict | None:
    return _decode_token(token, "mfa_challenge")


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="Telemed Secure")


def verify_totp_code(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_recovery_codes(count: int = 10) -> list[str]:
    return [secrets.token_hex(8).upper() for _ in range(count)]


def hash_recovery_code(code: str) -> str:
    normalized = code.strip().upper().encode("ascii")
    return hmac.new(
        SECRET_KEY.encode("utf-8"),
        b"telemed-secure-mfa-recovery-v1:" + normalized,
        hashlib.sha256,
    ).hexdigest()


def encrypt_medical_record(data: str) -> str:
    nonce = os.urandom(12)
    encrypted_data = AESGCM(AES_KEY).encrypt(nonce, data.encode("utf-8"), None)
    return base64.b64encode(nonce + encrypted_data).decode("ascii")


def decrypt_medical_record(encrypted_b64: str) -> str:
    raw_data = base64.b64decode(encrypted_b64.encode("ascii"), validate=True)
    if len(raw_data) < 12 + 16:
        raise ValueError("Données chiffrées invalides.")
    nonce, encrypted_data = raw_data[:12], raw_data[12:]
    return AESGCM(AES_KEY).decrypt(nonce, encrypted_data, None).decode("utf-8")
