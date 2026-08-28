from typing import Any, Dict, Protocol


class DocumentGeneratorProtocol(Protocol):
    """Boundary contract for the backend-only document generation engine (Target: F011-F020)."""

    def generate_pdf(self, template_name: str, payload: Dict[str, Any]) -> bytes: ...

    def generate_excel(self, template_name: str, payload: Dict[str, Any]) -> bytes: ...
