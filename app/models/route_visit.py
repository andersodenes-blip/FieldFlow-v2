import uuid

from sqlalchemy import ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantBase


class RouteVisit(TenantBase):
    __tablename__ = "route_visits"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    route_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("routes.id"), nullable=False)
    scheduled_visit_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("scheduled_visits.id"), nullable=False)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_drive_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
