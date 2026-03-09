# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from pydantic import BaseModel, EmailStr


class TokenRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Auth0CallbackResponse(BaseModel):
    access_token: str
    id_token: str
    org_id: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}
