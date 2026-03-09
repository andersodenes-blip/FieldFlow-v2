# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import calendar
import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from app.repositories.job_repository import JobRepository
from app.repositories.service_contract_repository import ServiceContractRepository


def _add_months(d: date, months: int) -> date:
    """Add months to a date, clamping to end of month if needed."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class JobGenerationService:
    def __init__(self, db: AsyncSession):
        self.job_repo = JobRepository(db)
        self.contract_repo = ServiceContractRepository(db)

    async def generate_jobs(
        self, tenant_id: uuid.UUID, horizon_days: int = 30
    ) -> tuple[int, list[uuid.UUID]]:
        horizon_date = date.today() + timedelta(days=horizon_days)

        # Get all active contracts due within the horizon
        contracts = await self.contract_repo.get_due_contracts(tenant_id, horizon_date)

        generated_ids: list[uuid.UUID] = []

        for contract in contracts:
            # Skip if there's already an unscheduled/scheduled job for this contract
            has_pending = await self.job_repo.has_pending_job_for_contract(
                contract.id, tenant_id
            )
            if has_pending:
                continue

            # Create job from contract
            job = Job(
                tenant_id=tenant_id,
                service_contract_id=contract.id,
                title=f"{contract.service_type} - Forfaller {contract.next_due_date}",
                status=JobStatus.unscheduled,
            )
            created_job = await self.job_repo.create(job)
            generated_ids.append(created_job.id)

            # Update next_due_date on the contract
            contract.next_due_date = _add_months(
                contract.next_due_date, contract.interval_months
            )
            await self.contract_repo.update(contract)

        return len(generated_ids), generated_ids
