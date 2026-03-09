# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.services.audit_service import AuditService


class CustomerService:
    def __init__(self, db: AsyncSession, user_id: uuid.UUID | None = None):
        self.repo = CustomerRepository(db)
        self.audit = AuditService(db)
        self.user_id = user_id

    async def create_customer(self, tenant_id: uuid.UUID, data: CustomerCreate) -> Customer:
        customer = Customer(
            tenant_id=tenant_id,
            name=data.name,
            org_number=data.org_number,
            contact_email=data.contact_email,
            contact_phone=data.contact_phone,
        )
        customer = await self.repo.create(customer)
        if self.user_id:
            await self.audit.log(tenant_id, self.user_id, "create", "customer", str(customer.id), data.model_dump())
        return customer

    async def list_customers(
        self,
        tenant_id: uuid.UUID,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "asc",
    ) -> tuple[list[Customer], int]:
        return await self.repo.get_all(
            tenant_id, search=search, page=page, page_size=page_size,
            sort_by=sort_by, sort_order=sort_order,
        )

    async def get_customer(self, customer_id: uuid.UUID, tenant_id: uuid.UUID) -> Customer:
        customer = await self.repo.get_by_id(customer_id, tenant_id)
        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        return customer

    async def get_customer_with_count(self, customer_id: uuid.UUID, tenant_id: uuid.UUID) -> dict:
        customer = await self.get_customer(customer_id, tenant_id)
        count = await self.repo.location_count(customer_id)
        return {"customer": customer, "location_count": count}

    async def update_customer(self, customer_id: uuid.UUID, tenant_id: uuid.UUID, data: CustomerUpdate) -> Customer:
        customer = await self.get_customer(customer_id, tenant_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(customer, field, value)
        customer = await self.repo.update(customer)
        if self.user_id:
            await self.audit.log(tenant_id, self.user_id, "update", "customer", str(customer.id), data.model_dump(exclude_unset=True))
        return customer

    async def delete_customer(self, customer_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        customer = await self.get_customer(customer_id, tenant_id)
        if await self.repo.has_active_contracts(customer.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete customer with active contracts",
            )
        if self.user_id:
            await self.audit.log(tenant_id, self.user_id, "delete", "customer", str(customer.id))
        await self.repo.delete(customer)
