# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.import_job import ImportJobResponse
from app.services.import_service import ImportService

router = APIRouter(prefix="/import", tags=["import"])


@router.post(
    "/customers",
    response_model=ImportJobResponse,
    status_code=201,
    dependencies=[require_role("org:admin")],
)
async def import_customers(
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    content = (await file.read()).decode("utf-8")
    service = ImportService(db)
    return await service.import_customers_csv(
        current_user.tenant_id,
        filename=file.filename or "upload.csv",
        content=content,
    )


@router.get("/{import_id}", response_model=ImportJobResponse)
async def get_import_status(
    import_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = ImportService(db)
    return await service.get_import_job(import_id, current_user.tenant_id)
