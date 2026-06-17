from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RBSoftware API"
    app_version: str = "0.1.0"
    environment: str = "development"

    database_url: str

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # Portal SSO — public key endpoint of the central auth service
    jwt_jwks_url: str = "https://id.miel-robotschool.com/auth/jwks"
    # Service token compartido portal↔plataformas (para /admin/roles)
    portal_service_token: str = "service-token-changeme"

    # WooCommerce integration (optional)
    woo_url: str | None = None
    woo_consumer_key: str | None = None
    woo_consumer_secret: str | None = None

    # MinIO / S3 storage
    minio_endpoint: str = "minio:9000"
    minio_public_endpoint: str = "localhost:8080"
    minio_public_scheme: str = "http"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "rbsoftware"
    minio_use_ssl: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()