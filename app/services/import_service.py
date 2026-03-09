# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import csv
import io
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.import_job import ImportJob, ImportStatus
from app.models.location import Location
from app.repositories.customer_repository import CustomerRepository
from app.repositories.import_job_repository import ImportJobRepository
from app.repositories.location_repository import LocationRepository

REQUIRED_COLUMNS = {"customer_name", "org_number", "contact_email", "address", "city", "postal_code"}


class ImportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.import_repo = ImportJobRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.location_repo = LocationRepository(db)

    async def import_customers_csv(
        self, tenant_id: uuid.UUID, filename: str, content: str
    ) -> ImportJob:
        # Create import job
        import_job = ImportJob(
            tenant_id=tenant_id,
            filename=filename,
            status=ImportStatus.pending,
        )
        import_job = await self.import_repo.create(import_job)

        # Update to processing
        import_job.status = ImportStatus.processing
        await self.import_repo.update(import_job)

        errors: list[dict] = []
        processed = 0
        created = 0
        updated = 0

        try:
            reader = csv.DictReader(io.StringIO(content))
            rows = list(reader)

            # Validate columns
            if reader.fieldnames:
                missing = REQUIRED_COLUMNS - set(reader.fieldnames)
                if missing:
                    import_job.status = ImportStatus.failed
                    import_job.error_log = {"errors": [{"row": 0, "error": f"Missing columns: {', '.join(missing)}"}]}
                    import_job.row_count = 0
                    await self.import_repo.update(import_job)
                    return import_job

            for i, row in enumerate(rows, start=1):
                processed += 1
                row_errors = []

                # Validate required fields
                if not row.get("customer_name", "").strip():
                    row_errors.append("customer_name is required")
                if not row.get("address", "").strip():
                    row_errors.append("address is required")
                if not row.get("city", "").strip():
                    row_errors.append("city is required")
                if not row.get("postal_code", "").strip():
                    row_errors.append("postal_code is required")

                if row_errors:
                    errors.append({"row": i, "errors": row_errors})
                    continue

                org_number = row.get("org_number", "").strip() or None
                contact_email = row.get("contact_email", "").strip() or None

                # Check for existing customer by org_number
                customer = None
                if org_number:
                    customer = await self.customer_repo.get_by_org_number(org_number, tenant_id)

                if customer:
                    # Update existing customer
                    customer.name = row["customer_name"].strip()
                    customer.contact_email = contact_email
                    await self.customer_repo.update(customer)
                    updated += 1
                else:
                    # Create new customer
                    customer = Customer(
                        tenant_id=tenant_id,
                        name=row["customer_name"].strip(),
                        org_number=org_number,
                        contact_email=contact_email,
                    )
                    customer = await self.customer_repo.create(customer)
                    created += 1

                # Create location
                location = Location(
                    tenant_id=tenant_id,
                    customer_id=customer.id,
                    address=row["address"].strip(),
                    city=row["city"].strip(),
                    postal_code=row["postal_code"].strip(),
                )
                self.db.add(location)
                await self.db.commit()
                await self.db.refresh(location)

            import_job.status = ImportStatus.completed if not errors else ImportStatus.failed
            import_job.row_count = processed
            import_job.error_log = {
                "created": created,
                "updated": updated,
                "errors": errors,
            }
            await self.import_repo.update(import_job)

        except Exception as e:
            import_job.status = ImportStatus.failed
            import_job.error_log = {"errors": [{"row": 0, "error": str(e)}]}
            await self.import_repo.update(import_job)

        return import_job

    async def get_import_job(
        self, job_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> ImportJob:
        job = await self.import_repo.get_by_id(job_id, tenant_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Import job not found",
            )
        return job
