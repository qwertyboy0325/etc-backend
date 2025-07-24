"""User schemas for API requests and responses."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr
    full_name: str = Field(
        ..., min_length=1, max_length=100, description="User's full name"
    )
    username: Optional[str] = Field(
        None, min_length=3, max_length=50, description="Username (optional)"
    )
    bio: Optional[str] = Field(None, max_length=500, description="User biography")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")


class UserCreate(UserBase):
    """Schema for user registration."""

    password: str = Field(
        ..., min_length=8, max_length=100, description="User password"
    )
    confirm_password: str = Field(..., description="Password confirmation")

    def validate_passwords_match(self) -> bool:
        """Validate that passwords match."""
        return self.password == self.confirm_password


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str = Field(..., min_length=1, description="User password")


class UserUpdate(BaseModel):
    """Schema for user profile updates."""

    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    bio: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=20)


class UserResponse(UserBase):
    """Schema for user data in responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    global_role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    email_verified_at: Optional[datetime] = None


class UserPublic(BaseModel):
    """Schema for public user information."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    username: Optional[str] = None
    bio: Optional[str] = None


class TokenResponse(BaseModel):
    """Schema for authentication token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserResponse


class TokenData(BaseModel):
    """Schema for JWT token data."""

    user_id: Optional[UUID] = None
    email: Optional[str] = None
    exp: Optional[datetime] = None


class PasswordChange(BaseModel):
    """Schema for password change requests."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(
        ..., min_length=8, max_length=100, description="New password"
    )
    confirm_new_password: str = Field(..., description="New password confirmation")

    def validate_passwords_match(self) -> bool:
        """Validate that new passwords match."""
        return self.new_password == self.confirm_new_password


class EmailVerification(BaseModel):
    """Schema for email verification."""

    token: str = Field(..., description="Email verification token")


class PasswordReset(BaseModel):
    """Schema for password reset request."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(
        ..., min_length=8, max_length=100, description="New password"
    )
    confirm_new_password: str = Field(..., description="New password confirmation")

    def validate_passwords_match(self) -> bool:
        """Validate that new passwords match."""
        return self.new_password == self.confirm_new_password


class UserStats(BaseModel):
    """Schema for user statistics."""

    model_config = ConfigDict(from_attributes=True)

    total_projects: int = 0
    active_projects: int = 0
    total_tasks_assigned: int = 0
    total_tasks_completed: int = 0
    total_annotations: int = 0
    completion_rate: float = 0.0
