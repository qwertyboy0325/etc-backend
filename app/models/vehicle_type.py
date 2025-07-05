"""Vehicle type model definitions."""

from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import relationship

from app.models.base import BaseProjectModel, BaseUUIDModel
from app.models.enums import VehicleTypeSource


class GlobalVehicleType(BaseUUIDModel):
    """Global vehicle type model for system-wide vehicle classifications."""

    __tablename__ = "global_vehicle_types"

    # Basic Information
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)

    # Category
    category = Column(String(50), nullable=True)  # e.g., "car", "truck", "motorcycle"

    # Ordering
    sort_order = Column(Integer, default=0, nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)  # System-defined types

    # Color for UI
    color = Column(String(7), nullable=True)  # Hex color code

    # Usage Statistics
    usage_count = Column(Integer, default=0, nullable=False)

    # Relationships
    project_vehicle_types = relationship(
        "ProjectVehicleType", back_populates="global_type", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<GlobalVehicleType(id={self.id}, name='{self.name}')>"

    @property
    def is_used(self) -> bool:
        """Check if this vehicle type is used in any project."""
        return self.usage_count > 0

    def increment_usage(self) -> None:
        """Increment usage count."""
        self.usage_count += 1

    def decrement_usage(self) -> None:
        """Decrement usage count."""
        if self.usage_count > 0:
            self.usage_count -= 1


class ProjectVehicleType(BaseProjectModel):
    """Project-specific vehicle type model."""

    __tablename__ = "project_vehicle_types"

    # Link to Global Type (optional)
    global_type_id = Column(
        PostgresUUID(as_uuid=True), ForeignKey("global_vehicle_types.id"), nullable=True
    )

    # Basic Information
    name = Column(String(100), nullable=False, index=True)
    display_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)

    # Source
    source = Column(
        Enum(VehicleTypeSource), default=VehicleTypeSource.PROJECT, nullable=False
    )

    # Category
    category = Column(String(50), nullable=True)

    # Ordering
    sort_order = Column(Integer, default=0, nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Color for UI
    color = Column(String(7), nullable=True)

    # Usage Statistics
    usage_count = Column(Integer, default=0, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="vehicle_types")

    global_type = relationship(
        "GlobalVehicleType", back_populates="project_vehicle_types"
    )

    annotations = relationship(
        "Annotation", back_populates="vehicle_type", cascade="all, delete-orphan"
    )

    # Unique constraint for project-specific names
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_project_vehicle_type_name"),
    )

    def __repr__(self) -> str:
        return f"<ProjectVehicleType(id={self.id}, project_id={self.project_id}, name='{self.name}')>"

    @property
    def is_global(self) -> bool:
        """Check if this is based on a global vehicle type."""
        return (
            self.source == VehicleTypeSource.GLOBAL and self.global_type_id is not None
        )

    @property
    def is_project_specific(self) -> bool:
        """Check if this is a project-specific vehicle type."""
        return self.source == VehicleTypeSource.PROJECT

    @property
    def is_used(self) -> bool:
        """Check if this vehicle type is used in annotations."""
        return self.usage_count > 0

    def increment_usage(self) -> None:
        """Increment usage count."""
        self.usage_count += 1

        # Also increment global type usage if linked
        if self.global_type:
            self.global_type.increment_usage()

    def decrement_usage(self) -> None:
        """Decrement usage count."""
        if self.usage_count > 0:
            self.usage_count -= 1

            # Also decrement global type usage if linked
            if self.global_type:
                self.global_type.decrement_usage()

    def sync_from_global(self) -> None:
        """Sync data from linked global vehicle type."""
        if self.global_type:
            self.display_name = self.global_type.display_name
            self.description = self.global_type.description
            self.category = self.global_type.category
            self.color = self.global_type.color

            # Update source
            self.source = VehicleTypeSource.GLOBAL

    @classmethod
    def create_from_global(
        cls, project_id: str, global_type: GlobalVehicleType
    ) -> "ProjectVehicleType":
        """Create a project vehicle type from a global vehicle type."""
        return cls(
            project_id=project_id,
            global_type_id=global_type.id,
            name=global_type.name,
            display_name=global_type.display_name,
            description=global_type.description,
            category=global_type.category,
            color=global_type.color,
            sort_order=global_type.sort_order,
            source=VehicleTypeSource.GLOBAL,
        )

    @classmethod
    def create_project_specific(
        cls, project_id: str, name: str, display_name: str, **kwargs
    ) -> "ProjectVehicleType":
        """Create a project-specific vehicle type."""
        return cls(
            project_id=project_id,
            name=name,
            display_name=display_name,
            source=VehicleTypeSource.PROJECT,
            **kwargs,
        )
