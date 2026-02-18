import hmac
import hashlib
import base64
import secrets
import requests
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient

from src.tool_registry.config import load_service_config

logger = logging.getLogger(__name__)

service_config = load_service_config()
bearer_scheme = HTTPBearer(auto_error=False)

JWKS_URL = "https://aai.egi.eu/auth/realms/egi/protocol/openid-connect/certs"
USERINFO_URL = "https://aai.egi.eu/auth/realms/egi/protocol/openid-connect/userinfo"
ISSUER = "https://aai.egi.eu/auth/realms/egi"  # token 'iss' claim


def _generate_admin_token(secret: str) -> str:
    digest = hmac.new(secret.encode(), b"admin-access", hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode()


ADMIN_TOKEN = _generate_admin_token(service_config.admin_auth_key)


jwk_client = PyJWKClient(JWKS_URL)


def fetch_user_info(token: str) -> dict:
    try:
        response = requests.get(
            USERINFO_URL, headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.debug(f"Userinfo fetch error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Failed to fetch user info"
        )


def validate_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    is_admin = validate_admin_token(credentials)
    if is_admin:
        return {"auth": "admin", "details": "Admin token valid"}
    return validate_egi_token(credentials)


def validate_egi_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    try:
        token = credentials.credentials
        # fetch signing key from JWKS based on 'kid' in token
        signing_key = jwk_client.get_signing_key_from_jwt(token).key

        # decode and validate
        payload = jwt.decode(token, signing_key, algorithms=["RS256"], issuer=ISSUER)
        user_info = fetch_user_info(token)
        payload["user_info"] = user_info  # attach user info to payload
        return payload  # optionally return payload for use in route

    except jwt.ExpiredSignatureError as e:
        logger.debug(f"Token expired: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )
    except jwt.InvalidTokenError as e:
        logger.debug(f"Token validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token invalid or missing"
        )
    except Exception as e:
        logger.debug(f"Token validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Error validating token"
        )


def validate_admin_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> bool:
    if credentials is None:
        return False

    return secrets.compare_digest(
        credentials.credentials,
        ADMIN_TOKEN,
    )


# def normal_auth() -> bool:
#     return False
#
#
# def require_auth_or_admin(
#     is_admin: bool = Depends(validate_admin_token),
#     user=Depends(normal_auth),
# ):
#     if is_admin:
#         return {"role": "admin"}
#
#     if not user:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
#
#     return user
