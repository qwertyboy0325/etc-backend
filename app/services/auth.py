"""Authentication service for user authentication and authorization."""

import logging
from datetime import datetime, timedelta
from typing import Optional, Union
from uuid import UUID

from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import create_access_token, pwd_context
from app.models.user import User
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service for user management and JWT operations."""

    def __init__(self, db: AsyncSession):
        """Initialize auth service with database session."""
        self.db = db

    def get_password_hash(self, password: str) -> str:
        """Generate password hash using bcrypt."""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        try:
            result = await self.db.execute(
                select(User).where(User.email == email, User.is_active == True)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching user by email {email}: {e}")
            return None

    async def get_user_by_id(self, user_id: Union[str, UUID]) -> Optional[User]:
        """Get user by ID."""
        try:
            if isinstance(user_id, str):
                user_id = UUID(user_id)

            result = await self.db.execute(
                select(User)
                .options(selectinload(User.project_memberships))
                .where(User.id == user_id, User.is_active == True)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching user by ID {user_id}: {e}")
            return None

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password."""
        user = await self.get_user_by_email(email)

        if not user:
            logger.warning(f"Authentication failed: User not found for email {email}")
            return None

        if not self.verify_password(password, user.hashed_password):
            logger.warning(f"Authentication failed: Invalid password for email {email}")
            return None

        if user.is_suspended:
            logger.warning(f"Authentication failed: User {email} is suspended")
            return None

        return user

    async def register_user(self, user_data: UserCreate) -> User:
        """Register a new user."""
        # Check if passwords match
        if not user_data.validate_passwords_match():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match"
            )

        # Check if user already exists
        existing_user = await self.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

        # Check username uniqueness if provided
        if user_data.username:
            result = await self.db.execute(
                select(User).where(User.username == user_data.username)
            )
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken",
                )

        try:
            # Create new user
            db_user = User(
                email=user_data.email,
                full_name=user_data.full_name,
                username=user_data.username,
                hashed_password=self.get_password_hash(user_data.password),
                bio=user_data.bio,
                phone=user_data.phone,
                is_active=True,
                is_verified=False,  # Email verification required
            )

            self.db.add(db_user)
            await self.db.commit()
            await self.db.refresh(db_user)

            logger.info(f"New user registered: {user_data.email}")
            return db_user

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error registering user {user_data.email}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to register user",
            )

    async def login_user(self, login_data: UserLogin) -> TokenResponse:
        """Login user and return JWT token."""
        user = await self.authenticate_user(login_data.email, login_data.password)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Update last login time
        user.last_login = datetime.utcnow()
        user.last_active = datetime.utcnow()
        await self.db.commit()

        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            subject=str(user.id), expires_delta=access_token_expires
        )

        logger.info(f"User logged in: {user.email}")

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
            user=UserResponse.model_validate(user),
        )

    def verify_token(self, token: str) -> Optional[dict]:
        """Verify JWT token and return payload."""
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )
            user_id: str = payload.get("sub")
            if user_id is None:
                return None
            return {"user_id": user_id, "payload": payload}
        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            return None

    async def get_current_user(self, token: str) -> Optional[User]:
        """Get current user from JWT token."""
        token_data = self.verify_token(token)
        if not token_data:
            return None

        user = await self.get_user_by_id(token_data["user_id"])
        if not user:
            logger.warning(f"User not found for token: {token_data['user_id']}")
            return None

        # Update last active time
        user.last_active = datetime.utcnow()
        await self.db.commit()

        return user

    async def refresh_token(self, current_user: User) -> TokenResponse:
        """Generate new access token for current user."""
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            subject=str(current_user.id), expires_delta=access_token_expires
        )

        logger.info(f"Token refreshed for user: {current_user.email}")

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(current_user),
        )

    async def update_password(
        self, user: User, current_password: str, new_password: str
    ) -> bool:
        """Update user password."""
        if not self.verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        try:
            user.hashed_password = self.get_password_hash(new_password)
            await self.db.commit()

            logger.info(f"Password updated for user: {user.email}")
            return True

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating password for user {user.email}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password",
            )

    async def deactivate_user(self, user: User) -> bool:
        """Deactivate user account."""
        try:
            user.is_active = False
            await self.db.commit()

            logger.info(f"User deactivated: {user.email}")
            return True

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deactivating user {user.email}: {e}")
            return False

    async def verify_user_email(self, user: User) -> bool:
        """Mark user email as verified."""
        try:
            user.is_verified = True
            user.email_verified_at = datetime.utcnow()
            await self.db.commit()

            logger.info(f"Email verified for user: {user.email}")
            return True

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error verifying email for user {user.email}: {e}")
            return False
