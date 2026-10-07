"""Configuración centralizada de la aplicación mediante Pydantic Settings."""

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

    # MinIO / S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ROOT_USER: str = "condo_minio_admin"
    MINIO_ROOT_PASSWORD: str = "condo_minio_secret"
    MINIO_BUCKET_VOUCHERS: str = "condomanager-vouchers"

    # JWT y Seguridad
    JWT_SECRET: str = "super_secret_condo_manager_jwt_key_development_only_2026_xyz"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Servidor
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # Pruebas: desactiva el pool de conexiones para evitar estados ligados a un event loop
    TESTING: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
