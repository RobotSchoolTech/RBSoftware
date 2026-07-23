from minio import Minio
from minio.error import S3Error
from io import BytesIO
from datetime import timedelta
import re
import uuid
from urllib.parse import quote
from app.core.config import settings

# ── Servido seguro de archivos subidos por usuarios ──────────────────────────
# Fuente ÚNICA de la política. Cualquier dominio (academic, training, …) que
# sirva un archivo que subió un usuario debe pasar por aquí, para no tener que
# repetir la allowlist y arriesgar drift entre módulos.

# Tabla única: extensión → (content-type servido, ¿se puede abrir inline?).
# Una sola fila por extensión para que agregar un tipo obligue a decidir las dos
# cosas a la vez; con dos estructuras separadas es cuestión de tiempo que alguien
# agregue la extensión a una y olvide la otra.
#
# Es una allowlist fail-closed: lo que no está aquí se sirve como descarga y con
# application/octet-stream. Filtrar por lo seguro-conocido — no por lista negra
# de lo peligroso — evita que un tipo ejecutable no contemplado (html, svg, xml…)
# se cuele como inline y ejecute script same-origin (XSS almacenado).
#
# Los videos son inline porque el visor de lecciones los reproduce embebidos: el
# navegador los decodifica como media, nunca como documento.
_FILE_POLICY: dict[str, tuple[str, bool]] = {
    #  ext        content-type          inline
    "pdf":      ("application/pdf",     True),
    "png":      ("image/png",           True),
    "jpg":      ("image/jpeg",          True),
    "jpeg":     ("image/jpeg",          True),
    "gif":      ("image/gif",           True),
    "webp":     ("image/webp",          True),
    "mp4":      ("video/mp4",           True),
    "webm":     ("video/webm",          True),
}

INLINE_SAFE_EXTENSIONS = frozenset(
    ext for ext, (_, inline) in _FILE_POLICY.items() if inline
)

_FALLBACK_CONTENT_TYPE = "application/octet-stream"


def extension_of(name: str | None) -> str:
    """Extensión en minúscula sin punto, o '' si no tiene."""
    if not name or "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()


def safe_content_type(file_name: str | None) -> str:
    """Content-type derivado de la EXTENSIÓN, nunca del cliente. Lo no
    conocido-seguro cae a application/octet-stream para que el navegador no lo
    interprete como algo ejecutable."""
    policy = _FILE_POLICY.get(extension_of(file_name))
    return policy[0] if policy else _FALLBACK_CONTENT_TYPE


def _resolve_serving(key: str, file_name: str | None) -> tuple[str, bool]:
    """Decide (content-type, inline) para un archivo, a partir de TODAS las
    extensiones que se conocen de él.

    El `key` lo genera el servidor y su extensión ya pasó validación; el
    `file_name` lo declara el cliente. Ninguno manda sobre el otro: se sirve
    inline solo si ambas extensiones conocidas coinciden y son seguras. Si
    divergen —un objeto `.html` registrado con el nombre `clase.mp4`— la
    discrepancia misma es la señal de sospecha, y el archivo cae a descarga.
    """
    extensions = {ext for ext in (extension_of(key), extension_of(file_name)) if ext}
    if len(extensions) != 1:
        return _FALLBACK_CONTENT_TYPE, False
    policy = _FILE_POLICY.get(extensions.pop())
    if policy is None:
        return _FALLBACK_CONTENT_TYPE, False
    return policy


def _attachment_disposition(download_name: str) -> str:
    """`Content-Disposition: attachment` con el nombre real del archivo.

    Se manda el nombre dos veces (RFC 6266): la forma cruda sin caracteres
    problemáticos para clientes viejos, y `filename*` con codificación
    porcentual para los acentos. Se sanea porque el nombre viene del cliente y
    sin escapar permitiría inyectar cabeceras.
    """
    ascii_name = re.sub(r'[^\w.\- ]', "_", download_name) or "archivo"
    quoted = quote(download_name, safe="")
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quoted}'


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

    def _generate_presigned_url(
        self,
        key: str,
        content_type: str,
        inline: bool,
        download_name: str,
        expires_seconds: int = 3600,
    ) -> str:
        """Primitiva interna. Los dominios NO deben llamarla: usan
        `generate_view_url` o `generate_download_url`, que son las que aplican la
        política de servido. Es privada a propósito — con un default de `inline`
        a mano es demasiado fácil reabrir el XSS sin que se note en review."""
        disposition = (
            "inline" if inline else _attachment_disposition(download_name)
        )
        response_headers = {
            "response-content-disposition": disposition,
            # Fuerza el content-type servido (firmado en la URL) en vez de confiar
            # en el que quedó guardado en el objeto. Cierra el vector de servir un
            # archivo con un content-type manipulado (p. ej. text/html) inline.
            "response-content-type": content_type,
        }
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

        Punto único donde se decide "esto se puede abrir en el navegador": sirve
        inline solo los tipos seguros-conocidos (PDF, imágenes y video) y todo lo
        demás como descarga (attachment). Además ancla el content-type servido
        desde la extensión —no desde el que quedó guardado en el objeto, que pudo
        fijar el cliente—. Cierra el XSS almacenado same-origin.
        """
        content_type, inline = _resolve_serving(key, file_name)
        return self._generate_presigned_url(
            key,
            content_type=content_type,
            inline=inline,
            download_name=file_name or key.split("/")[-1],
            expires_seconds=expires_seconds,
        )

    def generate_download_url(
        self,
        key: str,
        file_name: str | None = None,
        expires_seconds: int = 3600,
    ) -> str:
        """URL de DESCARGA (siempre attachment) para un archivo de un usuario.

        El `attachment` ya impide que el navegador lo interprete, pero se ancla
        igual el content-type desde la extensión para no depender del que el
        cliente fijó al subir. El archivo se descarga con su nombre real, no con
        el UUID del key.
        """
        content_type, _ = _resolve_serving(key, file_name)
        return self._generate_presigned_url(
            key,
            content_type=content_type,
            inline=False,
            download_name=file_name or key.split("/")[-1],
            expires_seconds=expires_seconds,
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
