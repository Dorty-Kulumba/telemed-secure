import os
import base64
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
import pyotp
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv

load_dotenv()

# Récupération des secrets depuis l'environnement (Règle : jamais de secrets dans le code)
SECRET_KEY = os.getenv("SECRET_KEY", "cle_secrete_par_defaut_a_changer")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Clé AES-GCM (doit faire 32 octets pour AES-256). Si non définie, on en génère une temporaire pour le test.
AES_KEY_ENV = os.getenv("AES_ENCRYPTION_KEY")
if AES_KEY_ENV:
    # On s'assure qu'elle est sous forme de bytes (encodée en base64 ou chaîne directe)
    try:
        AES_KEY = base64.b64decode(AES_KEY_ENV)
    except Exception:
        AES_KEY = AES_KEY_ENV.encode()[:32].ljust(32, b'\0')
else:
    AES_KEY = AESGCM.generate_key(bit_length=256)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 1. Hachage et vérification des mots de passe (Bcrypt)
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# 2. Gestion des Jetons d'Accès JWT
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# 3. Authentification Multifacteur (MFA / TOTP RFC 6238)
def generate_totp_secret() -> str:
    return pyotp.random_base32()

def verify_totp_code(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    # valid_window=1 permet d'accepter le code de la période précédente ou suivante (tolérance de 30s)
    return totp.verify(code, valid_window=1)

# 4. Chiffrement et Déchiffrement des Dossiers Médicaux (AES-GCM)
def encrypt_medical_record(data: str) -> str:
    aesgcm = AESGCM(AES_KEY)
    nonce = os.urandom(12)  # Nonce aléatoire de 12 octets recommandé pour GCM
    encrypted_data = aesgcm.encrypt(nonce, data.encode('utf-8'), None)
    # On retourne le nonce + le texte chiffré encodés en base64 pour le stockage en base de données
    return base64.b64encode(nonce + encrypted_data).decode('utf-8')

def decrypt_medical_record(encrypted_b64: str) -> str:
    aesgcm = AESGCM(AES_KEY)
    raw_data = base64.b64decode(encrypted_b64.encode('utf-8'))
    nonce = raw_data[:12]
    encrypted_data = raw_data[12:]
    decrypted_data = aesgcm.decrypt(nonce, encrypted_data, None)
    return decrypted_data.decode('utf-8')