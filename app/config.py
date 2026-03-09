# Copyright (c) 2026 Anders Ødenes. All rights reserved.
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://fieldflow:fieldflow@localhost:5432/fieldflow"
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Auth0 settings
    AUTH0_DOMAIN: str = ""
    AUTH0_CLIENT_ID: str = ""
    AUTH0_CLIENT_SECRET: str = ""
    AUTH0_AUDIENCE: str = ""
    AUTH0_CALLBACK_URL: str = "http://localhost:8000/auth/callback"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def auth0_enabled(self) -> bool:
        return bool(self.AUTH0_DOMAIN and self.AUTH0_CLIENT_ID and self.AUTH0_CLIENT_SECRET)


settings = Settings()
