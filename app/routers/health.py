# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"DB connection failed: {e}")
        db_status = "disconnected"
    return {"status": "ok", "db": db_status}
