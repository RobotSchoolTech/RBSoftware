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
from app.domains.training.services.training_service import (
    LESSON_FILE_EXTENSIONS,
    resolve_lesson_file_extension,
)


EJECUTABLES = ["html", "htm", "svg", "xml", "js", "xhtml", "mhtml"]


@pytest.fixture(autouse=True)
def _sin_lookup_de_region(monkeypatch):
    """Firmar una URL no requiere red salvo por la consulta de región del bucket,
    que el cliente hace la primera vez. Se fija para que los tests corran sin
    MinIO delante.

    Se usa un `assert`, no un `skip`: si un bump de `minio` renombra esta API
    privada, estos tests tienen que fallar ruidosamente. Un archivo de tests de
    seguridad que se auto-desactiva y deja CI en verde es peor que no tenerlo.
    """
    assert hasattr(storage_service.client, "_get_region"), (
        "la API de región del cliente MinIO cambió — revisar el fixture"
    )
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


@pytest.mark.parametrize(
    "key,file_name",
    [
        ("k/abc.pdf", "payload.html"),  # key inocente, archivo real ejecutable
        ("k/abc.html", "clase.pdf"),  # nombre inocente, objeto real ejecutable
        ("k/abc.html", "clase.mp4"),  # el caso del registro manipulado
    ],
)
def test_view_url_degrada_a_descarga_si_las_extensiones_divergen(key, file_name):
    # Ninguna de las dos fuentes manda sobre la otra: la discrepancia misma es la
    # señal de sospecha. Sirve inline solo si ambas coinciden y son seguras.
    q = _query(storage_service.generate_view_url(key, file_name))
    assert q["response-content-disposition"].startswith("attachment")
    assert q["response-content-type"] == "application/octet-stream"


def test_view_url_sin_extension_conocida_es_descarga():
    q = _query(storage_service.generate_view_url("k/sin_extension"))
    assert q["response-content-disposition"].startswith("attachment")
    assert q["response-content-type"] == "application/octet-stream"


def test_download_url_usa_el_nombre_real_del_archivo():
    url = storage_service.generate_download_url("k/9f2a-uuid.pdf", "Guía clase.pdf")
    disposition = _query(url)["response-content-disposition"]
    assert "9f2a-uuid.pdf" not in disposition
    assert "filename*=UTF-8''Gu%C3%ADa%20clase.pdf" in disposition


def test_download_name_no_permite_inyectar_cabeceras():
    disposition = _query(
        storage_service.generate_download_url(
            "k/x.pdf", 'evil".txt\r\nX-Injected: 1'
        )
    )["response-content-disposition"]
    assert "\r" not in disposition and "\n" not in disposition
    # La parte cruda del header queda saneada; el nombre completo solo viaja
    # codificado en filename*.
    assert 'filename="evil_.txt_' in disposition


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


# ── Validación del archivo de una lección ────────────────────────────────────
# Es el punto donde se cierra el XSS: sin esto, un .html anunciado como
# application/pdf entra al bucket con content-type text/html.


@pytest.mark.parametrize("nombre", ["payload.html", "x.svg", "a.pdf.html", "notas.txt"])
def test_leccion_pdf_rechaza_lo_que_no_es_pdf(nombre):
    with pytest.raises(ValueError):
        resolve_lesson_file_extension("PDF", nombre)


@pytest.mark.parametrize("nombre", ["clase.mov", "clase.avi", "payload.html"])
def test_leccion_video_rechaza_formatos_no_reproducibles(nombre):
    with pytest.raises(ValueError):
        resolve_lesson_file_extension("VIDEO", nombre)


@pytest.mark.parametrize("nombre", ["sin_extension", "", None])
def test_leccion_rechaza_archivo_sin_extension(nombre):
    with pytest.raises(ValueError):
        resolve_lesson_file_extension("PDF", nombre)


@pytest.mark.parametrize(
    "tipo,nombre,esperado",
    [
        ("PDF", "Guía de clase.pdf", "pdf"),
        ("PDF", "MAYUSCULAS.PDF", "pdf"),
        ("VIDEO", "clase.mp4", "mp4"),
        ("VIDEO", "clase.webm", "webm"),
        ("PDF", "a.html.pdf", "pdf"),  # solo cuenta la última extensión
    ],
)
def test_leccion_acepta_los_formatos_de_su_tipo(tipo, nombre, esperado):
    assert resolve_lesson_file_extension(tipo, nombre) == esperado


def test_leccion_desde_repositorio_rechaza_extensiones_divergentes():
    # El key lo generó el servidor y el nombre lo declaró el cliente: si no
    # coinciden, el archivo no es lo que dice ser.
    with pytest.raises(ValueError):
        resolve_lesson_file_extension("VIDEO", "repo/abc.html", "clase.mp4")


def test_el_mensaje_de_error_dice_que_formatos_se_admiten():
    with pytest.raises(ValueError, match=r"\.mp4, \.webm"):
        resolve_lesson_file_extension("VIDEO", "clase.mov")
