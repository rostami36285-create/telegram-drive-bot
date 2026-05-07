import base64
import hashlib
import json
from cryptography.fernet import Fernet
from config import ENCRYPTION_KEY


def _cipher() -> Fernet:
    if not ENCRYPTION_KEY:
        raise RuntimeError("ENCRYPTION_KEY در فایل .env تنظیم نشده است.")
    # همیشه SHA-256 می‌گیریم تا با داده‌های موجود در DB سازگار بمانیم.
    # تغییر این رفتار باعث می‌شود token های رمزنگاری‌شده قبلی قابل خواندن نباشند.
    key = base64.urlsafe_b64encode(hashlib.sha256(ENCRYPTION_KEY.encode()).digest())
    return Fernet(key)


def encrypt(data: dict) -> str:
    return _cipher().encrypt(json.dumps(data).encode()).decode()


def decrypt(token: str) -> dict:
    return json.loads(_cipher().decrypt(token.encode()).decode())


def encrypt_str(value: str) -> str:
    return _cipher().encrypt(value.encode()).decode()


def decrypt_str(token: str) -> str:
    return _cipher().decrypt(token.encode()).decode()
