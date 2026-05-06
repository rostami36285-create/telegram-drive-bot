import base64
import hashlib
import json
from cryptography.fernet import Fernet
from config import ENCRYPTION_KEY


def _cipher() -> Fernet:
    if not ENCRYPTION_KEY:
        raise RuntimeError("ENCRYPTION_KEY در فایل .env تنظیم نشده است.")
    key = base64.urlsafe_b64encode(hashlib.sha256(ENCRYPTION_KEY.encode()).digest())
    return Fernet(key)


def encrypt(data: dict) -> str:
    return _cipher().encrypt(json.dumps(data).encode()).decode()


def decrypt(token: str) -> dict:
    return json.loads(_cipher().decrypt(token.encode()).decode())
