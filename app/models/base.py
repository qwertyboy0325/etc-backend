"""Base model definitions."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.declarative import as_declarative, declared_attr


@as_declarative()
class Base:
    """Base model class for all database models."""

    id: Any
    __name__: str

    # Generate __tablename__ automatically
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()


class BaseUUIDModel(Base):
    """Base model with UUID primary key and timestamps."""

    __abstract__ = True

    id = Column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class BaseProjectModel(BaseUUIDModel):
    """Base model for project-related entities with project_id field."""

    __abstract__ = True

    project_id = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )
