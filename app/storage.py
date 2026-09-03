"""Service de stockage objet S3-compatible (MinIO) pour les miniatures des posts.

Toute la configuration vient de ``app.config.settings`` donc des variables
d'environnement (.env) — aucun identifiant en dur.
"""

import uuid
from functools import lru_cache
from urllib.parse import urlparse

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import settings

ALLOWED_THUMBNAIL_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
MAX_THUMBNAIL_SIZE = 5 * 1024 * 1024  # 5 Mo

_EXT_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _public_base_url() -> str:
    """URL publique racine (sans slash final) pour construire les URLs fichier."""
    base = (settings.minio_public_url or settings.minio_endpoint).rstrip("/")
    return base


def _endpoint_for_client() -> str:
    """Endpoint utilisé par boto3.

    En docker, ``minio_endpoint`` peut être ``http://localhost:9000`` (vu du host)
    alors que l'API doit joindre ``http://minio:9000``. On tente d'abord
    l'endpoint configuré, avec fallback automatique vers ``http://minio:9000``.
    """
    return settings.minio_endpoint.rstrip("/")


def _build_client(endpoint: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        region_name="us-east-1",
        config=BotoConfig(signature_version="s3v4"),
        verify=False if endpoint.startswith("http://") else True,
    )


@lru_cache(maxsize=1)
def get_s3_client():
    return _build_client(_endpoint_for_client())


def _candidate_endpoints() -> list[str]:
    primary = _endpoint_for_client()
    candidates = [primary]
    # Fallback docker-compose : le service s'appelle "minio".
    try:
        parsed = urlparse(primary)
        if parsed.hostname in ("localhost", "127.0.0.1"):
            scheme = parsed.scheme or "http"
            port = f":{parsed.port}" if parsed.port else ""
            candidates.append(f"{scheme}://minio{port}")
    except Exception:
        pass
    return candidates


def ensure_bucket() -> None:
    """Crée le bucket s'il n'existe pas (idempotent)."""
    last_err: Exception | None = None
    for endpoint in _candidate_endpoints():
        try:
            client = _build_client(endpoint)
            try:
                client.head_bucket(Bucket=settings.minio_bucket)
            except ClientError as e:
                code = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                err_code = e.response.get("Error", {}).get("Code", "")
                if code == 404 or err_code in ("404", "NoSuchBucket", "NotFound"):
                    client.create_bucket(Bucket=settings.minio_bucket)
                else:
                    raise
            # Rend le bucket lisible publiquement pour l'affichage des miniatures.
            try:
                client.put_bucket_policy(
                    Bucket=settings.minio_bucket,
                    Policy=(
                        '{"Version":"2012-10-17","Statement":[{"Effect":"Allow",'
                        '"Principal":{"AWS":["*"]},"Action":["s3:GetObject"],'
                        f'"Resource":["arn:aws:s3:::{settings.minio_bucket}/*"]}}}}'
                    ),
                )
            except ClientError:
                # Certains MinIO restreignent les policies : non bloquant.
                pass
            return
        except Exception as e:  # noqa: BLE001 - on tente le fallback suivant
            last_err = e
            continue
    raise RuntimeError(f"MinIO injoignable ({_candidate_endpoints()}): {last_err}")


def upload_thumbnail(data: bytes, content_type: str) -> str:
    """Upload un fichier image et retourne son URL publique."""
    if content_type not in ALLOWED_THUMBNAIL_TYPES:
        raise ValueError(
            f"Type de fichier non supporté : {content_type}. "
            "Formats acceptés : JPEG, PNG, WebP, GIF."
        )
    if len(data) > MAX_THUMBNAIL_SIZE:
        raise ValueError("Fichier trop volumineux (max 5 Mo).")
    if not data:
        raise ValueError("Fichier vide.")

    ensure_bucket()

    ext = _EXT_BY_TYPE[content_type]
    key = f"posts/{uuid.uuid4().hex}{ext}"

    last_err: Exception | None = None
    for endpoint in _candidate_endpoints():
        try:
            client = _build_client(endpoint)
            client.put_object(
                Bucket=settings.minio_bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
            return f"{_public_base_url()}/{settings.minio_bucket}/{key}"
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise RuntimeError(f"Échec de l'upload vers MinIO : {last_err}")


def delete_by_url(url: str) -> None:
    """Supprime un objet MinIO à partir de son URL publique (best-effort)."""
    try:
        prefix = f"{_public_base_url()}/{settings.minio_bucket}/"
        if not url.startswith(prefix):
            return
        key = url[len(prefix):]
        for endpoint in _candidate_endpoints():
            try:
                _build_client(endpoint).delete_object(
                    Bucket=settings.minio_bucket, Key=key
                )
                return
            except Exception:
                continue
    except Exception:
        pass
