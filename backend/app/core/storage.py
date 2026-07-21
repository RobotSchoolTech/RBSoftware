from minio import Minio
from minio.error import S3Error
from io import BytesIO
from datetime import timedelta
import uuid
from app.core.config import settings

class StorageService:

    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_use_ssl,
        )
        self.bucket = settings.minio_bucket

    def ensure_bucket_exists(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload_file(
        self,
        file_bytes: bytes,
        key: str,
        content_type: str,
    ) -> str:
        self.client.put_object(
            self.bucket, key,
            BytesIO(file_bytes), len(file_bytes),
            content_type=content_type,
        )
        return key

    def generate_presigned_url(
        self,
        key: str,
        expires_seconds: int = 3600,
        inline: bool = True,
        content_type: str | None = None,
    ) -> str:
        disposition = (
            "inline" if inline
            else f'attachment; filename="{key.split("/")[-1]}"'
        )
        response_headers = {
            "response-content-disposition": disposition,
        }
        # Fuerza el content-type servido (firmado en la URL) en vez de confiar en
        # el que quedó guardado en el objeto. Cierra el vector de servir un
        # archivo con un content-type manipulado (p. ej. text/html) inline.
        if content_type is not None:
            response_headers["response-content-type"] = content_type
        url = self.client.presigned_get_object(
            self.bucket, key,
            expires=timedelta(seconds=expires_seconds),
            response_headers=response_headers,
        )
        url = url.replace(
            f"http://{settings.minio_endpoint}",
            f"{settings.minio_public_scheme}://{settings.minio_public_endpoint}/storage",
            1,
        )
        return url

    def generate_presigned_put_url(self, key: str, expires_seconds: int = 3600) -> str:
        url = self.client.presigned_put_object(
            self.bucket,
            key,
            expires=timedelta(seconds=expires_seconds),
        )
        url = url.replace(
            f"http://{settings.minio_endpoint}",
            f"{settings.minio_public_scheme}://{settings.minio_public_endpoint}/storage",
            1,
        )
        return url

    def file_exists(self, key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except S3Error:
            return False

    def delete_file(self, key: str) -> None:
        try:
            self.client.remove_object(self.bucket, key)
        except S3Error:
            pass

storage_service = StorageService()
