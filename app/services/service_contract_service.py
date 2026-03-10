# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import calendar
import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_contract import ServiceContract
from app.repositories.location_repository import LocationRepository
from app.repositories.service_contract_repository import ServiceContractRepository
from app.schemas.service_contract import ServiceContractCreate, ServiceContractUpdate
from app.services.audit_service import AuditService


def _add_months(d: date, months: int) -> date:
    """Add months to a date, clamping to end of month if needed."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class ServiceContractService:
    def __init__(self, db: AsyncSession, user_id: uuid.UUID | None = None):
        self.repo = ServiceContractRepository(db)
        self.location_repo = LocationRepository(db)
        self.audit = AuditService(db)
        self.user_id = user_id

    async def create_contract(
        self, tenant_id: uuid.UUID, data: ServiceContractCreate
    ) -> ServiceContract:
        # Validate location belongs to tenant
        location = await self.location_repo.get_by_id(data.location_id, tenant_id)
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Location not found",
            )
        next_due = data.next_due_date
        if next_due is None:
            next_due = _add_months(date.today(), data.interval_months)
        contract = ServiceContract(
            tenant_id=tenant_id,
            location_id=data.location_id,
            service_type=data.service_type,
            interval_months=data.interval_months,
            next_due_date=next_due,
            sla_hours=data.sla_hours,
        )
        contract = await self.repo.create(contract)
        if self.user_id:
            await self.audit.log(tenant_id, self.user_id, "create", "service_contract", str(contract.id), data.model_dump(mode="json"))
        return contract

    async def list_contracts(
        self,
        tenant_id: uuid.UUID,
        location_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "asc",
    ) -> tuple[list[ServiceContract], int]:
        return await self.repo.get_all(
            tenant_id, location_id=location_id, customer_id=customer_id,
            is_active=is_active, page=page, page_size=page_size,
            sort_by=sort_by, sort_order=sort_order,
        )

    async def get_contract(
        self, contract_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> ServiceContract:
        contract = await self.repo.get_by_id(contract_id, tenant_id)
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service contract not found",
            )
        return contract

    async def update_contract(
        self, contract_id: uuid.UUID, tenant_id: uuid.UUID, data: ServiceContractUpdate
    ) -> ServiceContract:
        contract = await self.get_contract(contract_id, tenant_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(contract, field, value)
        contract = await self.repo.update(contract)
        if self.user_id:
            await self.audit.log(tenant_id, self.user_id, "update", "service_contract", str(contract.id), data.model_dump(exclude_unset=True, mode="json"))
        return contract

    async def delete_contract(
        self, contract_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> None:
        contract = await self.get_contract(contract_id, tenant_id)
        if self.user_id:
            await self.audit.log(tenant_id, self.user_id, "delete", "service_contract", str(contract.id))
        await self.repo.soft_delete(contract)
