from minio import Minio
from minio.error import S3Error
from io import BytesIO
from datetime import timedelta
import uuid
from app.core.config import settings

# ── Servido seguro de archivos subidos por usuarios ──────────────────────────
# Fuente ÚNICA de la política. Cualquier dominio (academic, training, …) que
# sirva un archivo que subió un usuario debe pasar por aquí, para no tener que
# repetir la allowlist y arriesgar drift entre módulos.

# Únicos tipos que se sirven inline (visor en el navegador). Allowlist
# fail-closed: cualquier otra cosa se sirve como descarga (attachment). Filtrar
# por lo seguro-conocido — no por lista negra de lo peligroso — evita que un
# tipo ejecutable no contemplado (html, svg, xml…) se cuele como inline y
# ejecute script same-origin (XSS almacenado).
INLINE_SAFE_EXTENSIONS = frozenset({"pdf", "png", "jpg", "jpeg", "gif", "webp"})

_CONTENT_TYPE_BY_EXTENSION = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}


def extension_of(name: str | None) -> str:
    """Extensión en minúscula sin punto, o '' si no tiene."""
    if not name or "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()


def safe_content_type(file_name: str | None) -> str:
    """Content-type derivado de la EXTENSIÓN, nunca del cliente. Lo no
    conocido-seguro cae a application/octet-stream para que el navegador no lo
    interprete como algo ejecutable."""
    return _CONTENT_TYPE_BY_EXTENSION.get(
        extension_of(file_name), "application/octet-stream"
    )


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

    def generate_view_url(
        self,
        key: str,
        file_name: str | None = None,
        expires_seconds: int = 3600,
    ) -> str:
        """URL de VISUALIZACIÓN segura para un archivo subido por un usuario.

        Punto único donde se decide "esto se puede abrir en el navegador":
        sirve inline solo los tipos seguros-conocidos (PDF e imágenes) y todo lo
        demás como descarga (attachment). Además ancla el content-type servido
        desde la extensión —no desde el que quedó guardado en el objeto, que
        pudo fijar el cliente—. Cierra el XSS almacenado same-origin.
        """
        ext = extension_of(file_name) or extension_of(key)
        return self.generate_presigned_url(
            key,
            expires_seconds=expires_seconds,
            inline=ext in INLINE_SAFE_EXTENSIONS,
            content_type=safe_content_type(file_name or key),
        )

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
