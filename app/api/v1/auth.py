"""Authentication API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import (
    get_auth_service,
    get_current_active_user,
    get_current_user,
    security,
)
from app.models.user import User
from app.schemas.user import (
    PasswordChange,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services.auth import AuthService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_data: UserCreate, auth_service: AuthService = Depends(get_auth_service)
) -> UserResponse:
    """
    Register a new user.

    - **email**: User's email address (must be unique)
    - **password**: User's password (minimum 8 characters)
    - **confirm_password**: Password confirmation (must match password)
    - **full_name**: User's full name
    - **username**: Optional username (must be unique if provided)
    - **bio**: Optional user biography
    - **phone**: Optional phone number
    """
    try:
        user = await auth_service.register_user(user_data)
        logger.info(f"New user registered successfully: {user.email}")
        return UserResponse.model_validate(user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin, auth_service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    """
    Login user and return access token.

    - **email**: User's email address
    - **password**: User's password

    Returns:
    - **access_token**: JWT token for authentication
    - **token_type**: Token type (bearer)
    - **expires_in**: Token expiration time in seconds
    - **user**: User information
    """
    try:
        token_response = await auth_service.login_user(login_data)
        logger.info(f"User logged in successfully: {login_data.email}")
        return token_response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error for {login_data.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """
    Refresh access token for current user.

    Requires valid authentication token.
    Returns new access token with extended expiration.
    """
    try:
        token_response = await auth_service.refresh_token(current_user)
        logger.info(f"Token refreshed for user: {current_user.email}")
        return token_response
    except Exception as e:
        logger.error(f"Token refresh error for {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """
    Get current authenticated user information.

    Requires valid authentication token.
    Returns detailed user profile information.
    """
    return UserResponse.model_validate(current_user)


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Logout current user.

    Note: Since we're using stateless JWT tokens, this endpoint
    mainly serves to validate the token and log the logout event.
    Client should discard the token after calling this endpoint.
    """
    try:
        logger.info(f"User logged out: {current_user.email}")
        return {"message": "Successfully logged out", "user_id": str(current_user.id)}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Logout failed"
        )


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """
    Change user password.

    - **current_password**: Current password
    - **new_password**: New password (minimum 8 characters)
    - **confirm_new_password**: New password confirmation

    Requires valid authentication token.
    """
    if not password_data.validate_passwords_match():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="New passwords do not match"
        )

    try:
        await auth_service.update_password(
            current_user, password_data.current_password, password_data.new_password
        )

        logger.info(f"Password changed for user: {current_user.email}")
        return {
            "message": "Password changed successfully",
            "user_id": str(current_user.id),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error for {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed",
        )


@router.post("/verify-token")
async def verify_token(current_user: User = Depends(get_current_user)) -> dict:
    """
    Verify if the provided token is valid.

    Returns user information if token is valid.
    Useful for client-side token validation.
    """
    return {
        "valid": True,
        "user_id": str(current_user.id),
        "email": current_user.email,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "global_role": current_user.global_role.value,
    }


@router.delete("/deactivate")
async def deactivate_account(
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """
    Deactivate current user account.

    This will mark the account as inactive.
    The user will need to contact an administrator to reactivate.
    """
    try:
        success = await auth_service.deactivate_user(current_user)
        if success:
            logger.info(f"Account deactivated: {current_user.email}")
            return {
                "message": "Account deactivated successfully",
                "user_id": str(current_user.id),
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to deactivate account",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Account deactivation error for {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account deactivation failed",
        )
