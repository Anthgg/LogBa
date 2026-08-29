"""Template Registry with Family Separation and Security Controls."""

from typing import Dict, List, Optional

from app.core.errors import DomainError
from app.shared.documents.schemas.manifest import TemplateManifest


class TemplateRegistry:
    """Internal registry mapping immutable template keys to verified templates and manifests."""

    _manifests: Dict[str, TemplateManifest] = {
        "base_document_v1": TemplateManifest(
            template_key="base_document_v1",
            family="base",
            version="1.0.0",
            title="Plantilla Canónica Base A4",
            description=(
                "Plantilla universal base con encabezado institucional, metadata, "
                "tablas paginadas, notas, QR, firma visual y pie de página con paginación."
            ),
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["DRAFT", "APPROVED", "ISSUED", "VOID"],
            created_at="2026-08-29T00:00:00Z",
        )
    }

    _template_files: Dict[str, str] = {
        "base_document_v1": "base/base_document_v1.html",
    }

    @classmethod
    def list_templates(cls, family: Optional[str] = None) -> List[TemplateManifest]:
        """Returns all registered template manifests, optionally filtered by family."""
        if family:
            return [m for m in cls._manifests.values() if m.family == family]
        return list(cls._manifests.values())

    @classmethod
    def get_manifest(cls, template_key: str) -> TemplateManifest:
        """Retrieves manifest for a registered template key."""
        if template_key not in cls._manifests:
            raise DomainError(
                code="TEMPLATE_NOT_FOUND",
                message=f"La plantilla documental '{template_key}' no se encuentra registrada.",
            )
        return cls._manifests[template_key]

    @classmethod
    def resolve_template_path(cls, template_key: str) -> str:
        """Resolves relative template file path safely against registry. Prevents path traversal."""
        if ".." in template_key or "/" in template_key or "\\" in template_key:
            raise DomainError(
                code="TEMPLATE_PATH_TRAVERSAL_DETECTED",
                message="Identificador de plantilla inválido o intento de path traversal.",
            )
        if template_key not in cls._template_files:
            raise DomainError(
                code="TEMPLATE_NOT_FOUND",
                message=f"La plantilla documental '{template_key}' no está disponible.",
            )
        return cls._template_files[template_key]
