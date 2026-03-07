import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantBase


class RouteStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    completed = "completed"


class Route(TenantBase):
    __tablename__ = "routes"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    region_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("regions.id"), nullable=False)
    route_date: Mapped[date] = mapped_column(Date, nullable=False)
    technician_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("technicians.id"), nullable=False)
    status: Mapped[RouteStatus] = mapped_column(Enum(RouteStatus), default=RouteStatus.draft)
