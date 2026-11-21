"""Configuración centralizada de la aplicación mediante Pydantic Settings."""

import os
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: Literal["development", "production"] = "development"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    DB_NULL_POOL: bool = False
    REDIS_REQUIRED: bool = True
    CRON_SECRET: SecretStr = SecretStr("")
    MAILJET_API_KEY: SecretStr = SecretStr("")
    MAILJET_SECRET: SecretStr = SecretStr("")
    MAILJET_FROM_EMAIL: str = ""
    MAILJET_ENABLED: bool = False
    MAILJET_WEBHOOK_SECRET: SecretStr = SecretStr("")
    VOUCHER_STORAGE: Literal["local", "supabase"] = "local"
    VOUCHER_MAX_BYTES: int = Field(default=5 * 1024 * 1024, ge=1, le=5 * 1024 * 1024)
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: SecretStr = SecretStr("")
    SUPABASE_STORAGE_BUCKET: str = "vouchers"
    # Base de Datos
    POSTGRES_USER: str = "condo_user"
    POSTGRES_PASSWORD: str = "condo_secret"
    POSTGRES_DB: str = "condomanager"
    DATABASE_URL: str = "postgresql+asyncpg://condo_user:condo_secret@localhost:5432/condomanager"
    DATABASE_URL_SYNC: str = "postgresql://condo_user:condo_secret@localhost:5432/condomanager"

    # Broker Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CUOTAS_DIA_EMISION: int = Field(default=1, ge=1, le=28)

    # MinIO / S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ROOT_USER: str = "condo_minio_admin"
    MINIO_ROOT_PASSWORD: str = "condo_minio_secret"
    MINIO_BUCKET_VOUCHERS: str = "condomanager-vouchers"

    # CON-22: evidencia privada local durante el prototipo (ruta relativa al proyecto).
    VOUCHERS_DIR: str = "uploads/vouchers"

    # JWT y Seguridad
    JWT_SECRET: str = "super_secret_condo_manager_jwt_key_development_only_2026_xyz"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=1)
    INVITACION_EXPIRE_HOURS: int = Field(default=24, ge=1, le=168)
    ACTIVACION_WEB_URL: str = "http://localhost:3000/activar"
    IDENTITY_DELIVERY_KEY: str = ""

    # Contexto del catálogo piloto; debe configurarse con el UUID creado por CON-2.
    CONDOMINIO_PILOTO_ID: str = ""
    DEMO_MODE: bool = False

    # Servidor
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    @model_validator(mode="after")
    def produccion_segura(self):
        if self.MAILJET_ENABLED and (
            not self.MAILJET_API_KEY.get_secret_value()
            or not self.MAILJET_SECRET.get_secret_value()
            or not self.MAILJET_FROM_EMAIL
            or len(self.MAILJET_WEBHOOK_SECRET.get_secret_value()) < 32
            or "@" not in self.MAILJET_FROM_EMAIL
            or any(c.isspace() for c in self.MAILJET_FROM_EMAIL)
        ):
            raise ValueError("Mailjet requiere claves privadas, remitente y secreto de callback >=32 caracteres.")
        if self.VOUCHER_STORAGE == "supabase" and (
            not self.SUPABASE_URL.startswith("https://")
            or not self.SUPABASE_SERVICE_ROLE_KEY.get_secret_value()
            or not self.SUPABASE_STORAGE_BUCKET
            or "/" in self.SUPABASE_STORAGE_BUCKET
        ):
            raise ValueError("Supabase Storage requiere URL HTTPS, clave privada y bucket válido.")
        if (self.APP_ENV == "production" or os.getenv("VERCEL_ENV") == "production") and (
            self.DEBUG or self.DEMO_MODE
            or len(self.JWT_SECRET) < 32 or self.JWT_SECRET.startswith("super_secret_")
            or not self.CORS_ORIGINS or any(
                "*" in origin or not origin.startswith("https://") for origin in self.CORS_ORIGINS
            )
            or not self.ACTIVACION_WEB_URL.startswith("https://")
            or self.VOUCHER_STORAGE != "supabase"
            or self.VOUCHER_MAX_BYTES > 3 * 1024 * 1024
            or len(self.CRON_SECRET.get_secret_value()) < 32
            or not self.DATABASE_URL.startswith("postgresql+asyncpg://")
            or urlsplit(self.DATABASE_URL).hostname in (None, "localhost", "127.0.0.1")
            or parse_qs(urlsplit(self.DATABASE_URL).query).get("ssl") not in (
                ["require"], ["verify-ca"], ["verify-full"],
            )
        ):
            raise ValueError("Configuración de producción insegura; revisar contrato Vercel Hobby.")
        return self

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )


settings = Settings()
