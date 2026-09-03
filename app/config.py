from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Blog API"
    database_url: str = "postgresql+psycopg://blog:blogpass@localhost:5432/blogdb"
    debug: bool = False

    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    cors_origins: str = "http://localhost:3000"

    # Emails promus automatiquement administrateurs à l'inscription
    # (liste séparée par des virgules). Ex. : "moi@exemple.com,admin@exemple.com"
    admin_emails: str = ""

    # --- Stockage objet S3 / MinIO (miniatures des posts) ---
    # Tout est configurable via .env pour rester sécurisé et dynamique.
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "noelson"
    # NOTE : MinIO impose un mot de passe d'au moins 8 caractères,
    # "noelson" (7) est refusé — l'instance locale utilise "noelson01".
    minio_secret_key: str = "noelson01"
    minio_bucket: str = "minuaturepost"
    minio_secure: bool = False
    # URL publique utilisée pour construire les URLs retournées par l'API.
    # En local : http://localhost:9000 ; en docker : http://minio:9000
    # Laisser vide pour dériver automatiquement depuis minio_endpoint.
    minio_public_url: str = ""


settings = Settings()
