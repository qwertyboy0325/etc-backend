"""Security utilities for authentication and authorization."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union

from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt

from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create access token for user authentication.

    Args:
        subject: Usually user ID or email
        expires_delta: Custom expiration time, defaults to settings value

    Returns:
        str: Encoded JWT token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "access",
        "iat": datetime.utcnow(),
    }

    try:
        encoded_jwt = jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating access token: {e}")
        raise


def create_refresh_token(subject: Union[str, Any]) -> str:
    """
    Create refresh token for token renewal.

    Args:
        subject: Usually user ID or email

    Returns:
        str: Encoded JWT refresh token
    """
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
        "iat": datetime.utcnow(),
    }

    try:
        encoded_jwt = jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating refresh token: {e}")
        raise


def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """
    Verify and decode JWT token.

    Args:
        token: JWT token to verify
        token_type: Expected token type ('access' or 'refresh')

    Returns:
        Optional[Dict[str, Any]]: Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )

        # Check token type
        if payload.get("type") != token_type:
            logger.warning(
                f"Invalid token type. Expected: {token_type}, Got: {payload.get('type')}"
            )
            return None

        # Check expiration
        if datetime.fromtimestamp(payload.get("exp", 0)) < datetime.utcnow():
            logger.warning("Token has expired")
            return None

        return payload

    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during token verification: {e}")
        return None


def get_password_hash(password: str) -> str:
    """
    Hash password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        str: Hashed password
    """
    try:
        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"Error hashing password: {e}")
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database

    Returns:
        bool: True if password matches, False otherwise
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False


def generate_password_reset_token(email: str) -> str:
    """
    Generate password reset token.

    Args:
        email: User email address

    Returns:
        str: Password reset token
    """
    delta = timedelta(hours=24)  # Reset token valid for 24 hours
    expire = datetime.utcnow() + delta

    to_encode = {
        "exp": expire,
        "sub": email,
        "type": "password_reset",
        "iat": datetime.utcnow(),
    }

    try:
        encoded_jwt = jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating password reset token: {e}")
        raise


def verify_password_reset_token(token: str) -> Optional[str]:
    """
    Verify password reset token and return email.

    Args:
        token: Password reset token

    Returns:
        Optional[str]: Email if token is valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )

        # Check token type
        if payload.get("type") != "password_reset":
            return None

        # Check expiration
        if datetime.fromtimestamp(payload.get("exp", 0)) < datetime.utcnow():
            return None

        return payload.get("sub")

    except JWTError:
        return None
    except Exception as e:
        logger.error(f"Error verifying password reset token: {e}")
        return None


def create_api_key() -> str:
    """
    Create API key for service-to-service authentication.

    Returns:
        str: API key
    """
    import secrets

    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """
    Hash API key for storage.

    Args:
        api_key: Plain API key

    Returns:
        str: Hashed API key
    """
    return get_password_hash(api_key)


def verify_api_key(plain_api_key: str, hashed_api_key: str) -> bool:
    """
    Verify API key against hash.

    Args:
        plain_api_key: Plain API key
        hashed_api_key: Hashed API key from database

    Returns:
        bool: True if API key matches, False otherwise
    """
    return verify_password(plain_api_key, hashed_api_key)
