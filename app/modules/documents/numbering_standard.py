import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.errors import DomainError, NotFoundError
from app.core.rbac import AuthenticatedPrincipal
from app.modules.documents.models import DocumentType
from app.modules.organization.models import Branch

# Canonical Numbering Standard Constants
DOCUMENT_NUMBERING_STANDARD = "TIPO-SEDE-AÑO-CORRELATIVO"
DOCUMENT_NUMBERING_PATTERN = "{TYPE}-{BRANCH}-{YEAR}-{SEQUENCE}"
DECISION_F012_CORRELATIVE_WIDTH = 6
REUSE_POLICY = "NEVER"
DISPLAY_CODE_UNIQUENESS_SCOPE = "ORGANIZATION"
ALLOCATION_PHASE = "FUTURE_PHASE_OWNER_F013"
ORGANIZATION_NUMBERING_CONFIGURATION = "FUTURE_PHASE_OWNER_F021"
MIN_PERIOD_YEAR = 2000
MAX_PERIOD_YEAR = 2100


class NumberingStandardSegment(BaseModel):
    key: str
    name: str
    description: str
    example: str
    source: str


class NumberingStandardSpecResponse(BaseModel):
    standard: str = DOCUMENT_NUMBERING_STANDARD
    pattern: str = DOCUMENT_NUMBERING_PATTERN
    correlative_width: int = DECISION_F012_CORRELATIVE_WIDTH
    reuse_policy: str = REUSE_POLICY
    uniqueness_scope: str = DISPLAY_CODE_UNIQUENESS_SCOPE
    allocation_phase: str = ALLOCATION_PHASE
    official_number_preservation: bool = True
    segments: List[NumberingStandardSegment] = Field(
        default_factory=lambda: [
            NumberingStandardSegment(
                key="TYPE",
                name="Tipo Documental",
                description=(
                    "Código alfanumérico del catálogo de tipos documentales (ej: PO, REQ, GRN)"
                ),
                example="PO",
                source="document_types.code",
            ),
            NumberingStandardSegment(
                key="BRANCH",
                name="Sede Operativa",
                description=(
                    "Código alfanumérico de la sede o sucursal emisora (ej: LIM, AQP, DEMO-LIM)"
                ),
                example="LIM",
                source="branches.code",
            ),
            NumberingStandardSegment(
                key="YEAR",
                name="Año del Periodo",
                description=(
                    "Año de 4 dígitos correspondiente a la fecha de emisión del documento"
                ),
                example="2026",
                source="period_year (YYYY)",
            ),
            NumberingStandardSegment(
                key="SEQUENCE",
                name="Correlativo Numérico",
                description=(
                    "Secuencia incremental con ceros según el ancho configurado (6 dígitos)"
                ),
                example="000001",
                source="correlative (1..999999)",
            ),
        ]
    )
    examples: List[str] = Field(
        default_factory=lambda: [
            "PO-LIM-2026-000001",
            "REQ-LIM-2026-000042",
            "ODS-AQP-2026-001527",
            "GRN-DEMO-LIM-2026-000100",
        ]
    )


class StructuredDocumentIdentity(BaseModel):
    organization_id: uuid.UUID
    document_type_id: uuid.UUID
    document_type_code: str
    branch_id: uuid.UUID
    branch_code: str
    period_year: int
    correlative: int
    display_code: str


class DocumentNumberingPreviewRequest(BaseModel):
    document_type_id: uuid.UUID = Field(..., description="ID del tipo documental interno")
    branch_id: uuid.UUID = Field(..., description="ID de la sede emisora")
    period_year: Optional[int] = Field(
        None, description="Año del periodo documental (default: año UTC actual)"
    )
    sample_correlative: int = Field(
        1, ge=1, le=999999, description="Correlativo de ejemplo para la vista previa"
    )


class DocumentNumberingPreviewResponse(BaseModel):
    preview: str
    format_pattern: str = DOCUMENT_NUMBERING_PATTERN
    structured_identity: StructuredDocumentIdentity
    reserved: bool = False
    allocated: bool = False
    message: str = (
        "Vista previa del estándar. Este número NO está reservado ni asignado "
        "(FUTURE_PHASE_OWNER_F013)."
    )


def format_canonical_document_code(
    type_code: str,
    branch_code: str,
    period_year: int,
    correlative: int,
    width: int = DECISION_F012_CORRELATIVE_WIDTH,
) -> str:
    """Format canonical document display code: {TYPE}-{BRANCH}-{YEAR}-{SEQUENCE}."""
    clean_type = type_code.strip().upper()
    clean_branch = branch_code.strip().upper()
    padded_seq = f"{correlative:0{width}d}"
    return f"{clean_type}-{clean_branch}-{period_year:04d}-{padded_seq}"


class DocumentNumberingService:
    """Domain service for Document Numbering Standard validation and preview generation."""

    @staticmethod
    def get_standard_spec() -> NumberingStandardSpecResponse:
        return NumberingStandardSpecResponse()

    @staticmethod
    def preview_numbering(
        db: Session,
        principal: AuthenticatedPrincipal,
        payload: DocumentNumberingPreviewRequest,
    ) -> DocumentNumberingPreviewResponse:
        # 1. Resolve & Validate Document Type
        doc_type = db.get(DocumentType, payload.document_type_id)
        if not doc_type:
            raise NotFoundError(
                message="El tipo documental especificado no existe.",
                code="DOCUMENT_TYPE_NOT_FOUND",
            )
        if not doc_type.is_active:
            raise DomainError(
                code="DOCUMENT_TYPE_INACTIVE",
                message=f"El tipo documental '{doc_type.code}' se encuentra inactivo.",
            )
        if doc_type.document_scope != "INTERNAL":
            raise DomainError(
                code="EXTERNAL_OFFICIAL_NUMBER_MUST_BE_PRESERVED",
                message=(
                    f"El tipo documental '{doc_type.code}' tiene alcance EXTERNAL. "
                    "Los documentos externos preservan su serie y número de origen legal "
                    "y no admiten codificación interna TIPO-SEDE-AÑO-CORRELATIVO."
                ),
            )

        # 2. Resolve & Validate Branch
        branch = db.get(Branch, payload.branch_id)
        if not branch:
            raise NotFoundError(
                message="La sede especificada no existe.",
                code="BRANCH_NOT_FOUND",
            )
        if principal.organization_id and branch.organization_id != principal.organization_id:
            raise DomainError(
                code="BRANCH_ORGANIZATION_MISMATCH",
                message=(
                    "La sede especificada no pertenece a la organización del usuario autenticado."
                ),
            )

        # 3. Validate Period Year
        year = payload.period_year or datetime.now(timezone.utc).year
        if year < MIN_PERIOD_YEAR or year > MAX_PERIOD_YEAR:
            raise DomainError(
                code="INVALID_DOCUMENT_PERIOD_YEAR",
                message=(
                    f"El año del periodo {year} se encuentra fuera del rango permitido "
                    f"({MIN_PERIOD_YEAR}..{MAX_PERIOD_YEAR})."
                ),
            )

        # 4. Validate Correlative
        correlative = payload.sample_correlative
        if correlative < 1 or correlative > 999999:
            raise DomainError(
                code="INVALID_CORRELATIVE",
                message="El correlativo debe ser un entero positivo mayor o igual a 1.",
            )

        # 5. Build Canonical Display Code and Structured Identity
        display_code = format_canonical_document_code(
            type_code=doc_type.code,
            branch_code=branch.code,
            period_year=year,
            correlative=correlative,
        )

        identity = StructuredDocumentIdentity(
            organization_id=branch.organization_id,
            document_type_id=doc_type.id,
            document_type_code=doc_type.code,
            branch_id=branch.id,
            branch_code=branch.code,
            period_year=year,
            correlative=correlative,
            display_code=display_code,
        )

        return DocumentNumberingPreviewResponse(
            preview=display_code,
            structured_identity=identity,
            reserved=False,
            allocated=False,
        )
