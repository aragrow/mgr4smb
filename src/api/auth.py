"""
JWT Authentication for Orchestrator API

Provides secure authentication using JWT tokens with auto-renewal
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from fastapi import HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from src.config.settings import get_settings


class TokenPayload(BaseModel):
    """JWT token payload"""
    client_id: str
    exp: int  # Unix timestamp
    iat: int  # Unix timestamp
    sub: str = "orchestrator_access"


class ClientCredentials(BaseModel):
    """Client credentials for authentication"""
    client_id: str
    client_secret: str


class TokenResponse(BaseModel):
    """Token response model"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    expires_at: datetime


def create_access_token(client_id: str, expires_delta: Optional[timedelta] = None) -> Dict[str, Any]:
    """
    Create a new JWT access token

    Args:
        client_id: Client identifier
        expires_delta: Token expiration time (default: 24 hours)

    Returns:
        Dictionary with token and expiration info
    """
    settings = get_settings()

    if expires_delta is None:
        expires_delta = timedelta(hours=24)  # Default 24 hours

    now = datetime.utcnow()
    expire = now + expires_delta

    payload = {
        "client_id": client_id,
        "exp": expire,
        "iat": now,
        "sub": "orchestrator_access",
    }

    # Create JWT token
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": int(expires_delta.total_seconds()),
        "expires_at": expire,
    }


def verify_token(token: str) -> TokenPayload:
    """
    Verify JWT token and return payload

    Args:
        token: JWT token string

    Returns:
        Token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        # Check if token is expired
        exp = datetime.fromtimestamp(payload["exp"])
        if datetime.utcnow() > exp:
            raise HTTPException(
                status_code=401,
                detail="Token has expired"
            )

        return TokenPayload(**payload)

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        # Invalid token format, signature mismatch, or other JWT errors
        raise HTTPException(
            status_code=401,
            detail=f"Could not validate credentials: Invalid token - {str(e)}"
        )
    except jwt.DecodeError as e:
        # Token cannot be decoded
        raise HTTPException(
            status_code=401,
            detail=f"Could not validate credentials: Decode error - {str(e)}"
        )
    except Exception as e:
        # Catch-all for unexpected errors
        raise HTTPException(
            status_code=401,
            detail=f"Could not validate credentials: {type(e).__name__} - {str(e)}"
        )


def verify_client_credentials(client_id: str, client_secret: str) -> bool:
    """
    Verify client credentials against stored credentials

    Args:
        client_id: Client identifier
        client_secret: Client secret

    Returns:
        True if credentials are valid

    Raises:
        HTTPException: If credentials are invalid
    """
    settings = get_settings()

    # Parse API clients from settings
    api_clients = {}
    if settings.api_clients_raw:
        for pair in settings.api_clients_raw.split(","):
            if "=" in pair:
                cid, secret = pair.strip().split("=", 1)
                api_clients[cid.strip()] = secret.strip()

    # Get stored credentials for this client
    stored_secret = api_clients.get(client_id)

    if not stored_secret:
        raise HTTPException(
            status_code=401,
            detail="Invalid client credentials"
        )

    if stored_secret != client_secret:
        raise HTTPException(
            status_code=401,
            detail="Invalid client credentials"
        )

    return True


def should_renew_token(token_payload: TokenPayload) -> bool:
    """
    Check if token should be renewed (less than 1 hour remaining)

    Args:
        token_payload: Token payload

    Returns:
        True if token should be renewed
    """
    now_timestamp = datetime.utcnow().timestamp()
    time_remaining = token_payload.exp - now_timestamp
    return time_remaining < 3600  # Less than 1 hour


class JWTBearer(HTTPBearer):
    """
    FastAPI dependency for JWT authentication

    Automatically verifies JWT tokens and supports auto-renewal
    """

    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> TokenPayload:
        """
        Verify JWT token from request

        Args:
            request: FastAPI request

        Returns:
            Token payload

        Raises:
            HTTPException: If token is invalid
        """
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)

        if credentials:
            if not credentials.scheme == "Bearer":
                raise HTTPException(
                    status_code=403,
                    detail="Invalid authentication scheme"
                )

            # Verify token
            token_payload = verify_token(credentials.credentials)

            # Add renewal hint to response headers if needed
            if should_renew_token(token_payload):
                # Add custom header to indicate renewal needed
                request.state.should_renew_token = True

            return token_payload
        else:
            raise HTTPException(
                status_code=403,
                detail="Invalid authorization code"
            )
