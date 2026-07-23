"""Política de servido seguro de archivos subidos por usuarios.

Fija el comportamiento que cierra el XSS almacenado same-origin: solo los tipos
seguros-conocidos se sirven inline, y el content-type servido siempre sale de la
extensión, nunca del que el cliente fijó al subir.
"""
import os
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-only")

import pytest

from app.core.storage import (
    INLINE_SAFE_EXTENSIONS,
    extension_of,
    safe_content_type,
    storage_service,
)
from app.domains.training.services.training_service import LESSON_FILE_EXTENSIONS


EJECUTABLES = ["html", "htm", "svg", "xml", "js", "xhtml", "mhtml"]


@pytest.fixture(autouse=True)
def _sin_lookup_de_region(monkeypatch):
    """Firmar una URL no requiere red salvo por la consulta de región del bucket,
    que el cliente hace la primera vez. Se fija para que los tests corran sin
    MinIO delante."""
    if not hasattr(storage_service.client, "_get_region"):
        pytest.skip("la API de región del cliente MinIO cambió")
    monkeypatch.setattr(
        type(storage_service.client), "_get_region", lambda *a, **k: "us-east-1"
    )


def _query(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


@pytest.mark.parametrize("ext", EJECUTABLES)
def test_tipos_ejecutables_nunca_son_inline(ext):
    assert ext not in INLINE_SAFE_EXTENSIONS


@pytest.mark.parametrize("ext", EJECUTABLES)
def test_content_type_de_ejecutables_es_octet_stream(ext):
    assert safe_content_type(f"payload.{ext}") == "application/octet-stream"


def test_extension_se_normaliza_a_minuscula():
    assert extension_of("Informe.PDF") == "pdf"
    assert extension_of("sin_extension") == ""
    assert extension_of(None) == ""


def test_view_url_de_html_fuerza_descarga():
    url = storage_service.generate_view_url("k/abc.html", "payload.html")
    q = _query(url)
    assert q["response-content-disposition"].startswith("attachment")
    assert q["response-content-type"] == "application/octet-stream"


def test_view_url_ignora_la_extension_del_key_si_hay_file_name():
    # El key puede haber quedado con una extensión inocente mientras el archivo
    # real es ejecutable: manda el nombre declarado del archivo.
    url = storage_service.generate_view_url("k/abc.pdf", "payload.html")
    assert _query(url)["response-content-disposition"].startswith("attachment")


@pytest.mark.parametrize(
    "file_name,content_type",
    [
        ("clase.pdf", "application/pdf"),
        ("foto.png", "image/png"),
        ("video.mp4", "video/mp4"),
        ("video.webm", "video/webm"),
    ],
)
def test_view_url_de_tipos_seguros_es_inline_con_content_type_anclado(
    file_name, content_type
):
    q = _query(storage_service.generate_view_url(f"k/x", file_name))
    assert q["response-content-disposition"] == "inline"
    assert q["response-content-type"] == content_type


def test_download_url_siempre_es_attachment():
    q = _query(storage_service.generate_download_url("k/abc.pdf", "clase.pdf"))
    assert q["response-content-disposition"].startswith("attachment")
    assert q["response-content-type"] == "application/pdf"


def test_extensiones_de_leccion_son_subconjunto_de_las_servibles_inline():
    # Lo que se admite subir como lección tiene que poder mostrarse en el visor;
    # si no, el archivo quedaría inaccesible desde la UI que lo creó.
    for extensiones in LESSON_FILE_EXTENSIONS.values():
        assert extensiones <= INLINE_SAFE_EXTENSIONS
