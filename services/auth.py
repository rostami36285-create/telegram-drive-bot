from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, OAUTH_REDIRECT_URI

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

_CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [OAUTH_REDIRECT_URI],
    }
}


def _flow() -> Flow:
    return Flow.from_client_config(_CLIENT_CONFIG, scopes=SCOPES, redirect_uri=OAUTH_REDIRECT_URI)


def get_auth_url(state: str) -> str:
    flow = _flow()
    url, _ = flow.authorization_url(access_type="offline", state=state, prompt="consent")
    return url


def exchange_code(code: str) -> dict:
    flow = _flow()
    flow.fetch_token(code=code)
    return _to_dict(flow.credentials)


def get_credentials(tokens: dict) -> Credentials:
    creds = Credentials(
        token=tokens["token"],
        refresh_token=tokens["refresh_token"],
        token_uri=tokens["token_uri"],
        client_id=tokens["client_id"],
        client_secret=tokens["client_secret"],
        scopes=tokens["scopes"],
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def _to_dict(creds: Credentials) -> dict:
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
    }


def creds_to_dict(creds: Credentials) -> dict:
    return _to_dict(creds)
