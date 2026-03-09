# Copyright (c) 2026 Anders Ødenes. All rights reserved.
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import Auth0CallbackResponse, TokenRequest, TokenResponse, UserResponse
from app.services.auth_service import authenticate_user, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
async def login(form: TokenRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await authenticate_user(db, form.email, form.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(str(user.id), str(user.tenant_id), user.role.value)
    return TokenResponse(access_token=token)


@router.get("/login")
async def auth0_login(state: str | None = None):
    """Redirect to Auth0 Universal Login for authentication."""
    if not settings.auth0_enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Auth0 is not configured",
        )
    from app.services.auth0_service import build_authorize_url

    url = build_authorize_url(state=state)
    return RedirectResponse(url=url)


@router.get("/callback", response_model=Auth0CallbackResponse)
async def auth0_callback(code: Annotated[str, Query()]):
    """Handle Auth0 callback after authentication."""
    if not settings.auth0_enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Auth0 is not configured",
        )
    from app.services.auth0_service import exchange_code_for_tokens, verify_auth0_token

    try:
        tokens = await exchange_code_for_tokens(code)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to exchange authorization code",
        )

    access_token = tokens.get("access_token")
    id_token = tokens.get("id_token")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No access token received from Auth0",
        )

    try:
        payload = await verify_auth0_token(access_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token from Auth0",
        )

    return Auth0CallbackResponse(
        access_token=access_token,
        id_token=id_token or "",
        org_id=payload.get("org_id", ""),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user
