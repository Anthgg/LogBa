"""WeasyPrint PDF Rendering Engine with Local-Only URL Fetcher."""

import io
from typing import Any, Dict, Optional

import weasyprint

from app.core.errors import DomainError


def local_only_url_fetcher(url: str, timeout: int = 10, ssl_context: Any = None) -> Dict[str, Any]:
    """Strict URL fetcher blocking SSRF by denying all external HTTP/HTTPS network requests."""
    if url.startswith("http://") or url.startswith("https://") or url.startswith("ftp://"):
        raise DomainError(
            code="PDF_RENDERER_SSRF_BLOCKED",
            message=f"Solicitud de red externa bloqueada en renderer PDF: {url}",
        )
    return weasyprint.default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)


class WeasyPrintPdfRenderer:
    """Generates PDF byte stream from HTML string using WeasyPrint."""

    @staticmethod
    def render_pdf(
        html_content: str,
        title: Optional[str] = None,
        author: str = "Sistema Logistico Integral",
    ) -> bytes:
        """Compiles HTML+CSS into standard A4 PDF bytes."""
        try:
            html = weasyprint.HTML(
                string=html_content,
                url_fetcher=local_only_url_fetcher,
            )
            buf = io.BytesIO()
            html.write_pdf(target=buf)
            return buf.getvalue()
        except DomainError:
            raise
        except Exception as e:
            raise DomainError(
                code="PDF_COMPILATION_ERROR",
                message=f"Fallo al compilar documento PDF: {str(e)}",
            ) from e
