# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class RoutePlanRequest(BaseModel):
    region_id: uuid.UUID
    start_date: date
    end_date: date


class RoutePlanResponse(BaseModel):
    routes_created: int
    visits_assigned: int
    jobs_without_coords: int
    capacity_warnings: list[str]


class RouteVisitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence_order: int
    estimated_drive_minutes: int | None = None
    job_id: uuid.UUID
    job_title: str
    location_address: str
    latitude: float | None = None
    longitude: float | None = None
    estimated_work_hours: float


class RouteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    region_id: uuid.UUID
    route_date: date
    technician_id: uuid.UUID
    technician_name: str
    status: str
    total_hours: float
    total_km: float
    visits: list[RouteVisitResponse]
    created_at: datetime
    updated_at: datetime


class RouteListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    route_date: date
    technician_id: uuid.UUID
    technician_name: str
    status: str
    visit_count: int
    total_hours: float


class RouteStatusUpdate(BaseModel):
    status: str
