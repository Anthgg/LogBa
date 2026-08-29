"""Jinja2 HTML Template Rendering Engine with Security Guards."""

import pathlib
from typing import Any, Dict

import jinja2

from app.core.errors import DomainError
from app.shared.documents.templates.registry import TemplateRegistry

TEMPLATES_ROOT = pathlib.Path(__file__).parent.parent / "templates"


class SecureTemplateEngine:
    """Renders Jinja2 HTML templates securely with autoescape and strict boundaries."""

    def __init__(self) -> None:
        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(TEMPLATES_ROOT)),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
            undefined=jinja2.StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_html(self, template_key: str, context_dict: Dict[str, Any]) -> str:
        """Renders HTML template from context dictionary."""
        relative_path = TemplateRegistry.resolve_template_path(template_key)
        try:
            template = self._env.get_template(relative_path)
            return template.render(**context_dict)
        except jinja2.TemplateNotFound as e:
            raise DomainError(
                code="TEMPLATE_FILE_NOT_FOUND",
                message=f"El archivo de plantilla '{relative_path}' no fue encontrado.",
            ) from e
        except jinja2.TemplateError as e:
            raise DomainError(
                code="TEMPLATE_RENDER_ERROR",
                message=f"Error al evaluar la plantilla '{template_key}': {str(e)}",
            ) from e
