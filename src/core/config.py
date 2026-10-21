"""Configuración centralizada de la aplicación mediante Pydantic Settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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

    # JWT y Seguridad
    JWT_SECRET: str = "super_secret_condo_manager_jwt_key_development_only_2026_xyz"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Contexto del catálogo piloto; debe configurarse con el UUID creado por CON-2.
    CONDOMINIO_PILOTO_ID: str = ""
    DEMO_MODE: bool = False

    # Notificaciones y Transporte (CON-32 / CON-37)
    NOTIFICACIONES_TRANSPORTE: str = "SIMULADO"
    NOTIFICACIONES_LEASE_SEGUNDOS: int = Field(default=60, ge=5, le=3600)
    NOTIFICACIONES_LOTE_LIMITE: int = Field(default=50, ge=1, le=500)
    NOTIFICACIONES_INTERVALO_DESPACHO_SEGUNDOS: int = Field(default=5, ge=1, le=300)
    # Cuentas reales de recaudación del condominio; sin ellas el aviso remite a la plataforma.
    NOTIFICACIONES_MEDIOS_PAGO: str = (
        "Consulte las cuentas de recaudación vigentes en CondoManager > Pagos."
    )
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "notificaciones@condomanager.pe"
    SMTP_USE_TLS: bool = False
    SMTP_TIMEOUT_SEGUNDOS: int = 10

    # Servidor
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
