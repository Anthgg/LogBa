# Contratos Internos y Manejo Universal de Errores

Este documento define los contratos de interfaz entre capas y el esquema universal de respuestas y excepciones para el **Sistema Logístico Integral**.

---

## 1. Jerarquía Canónica de Excepciones de Dominio

Todas las excepciones de negocio heredan de `DomainError` (`app/core/errors.py`):

```text
DomainError (Base, 400)
 ├── NotFoundError (404, NOT_FOUND)
 ├── ConflictError (409, CONFLICT)
 ├── ValidationError (422, VALIDATION_ERROR)
 ├── DependencyRequiredError (409, DEPENDENCY_REQUIRED)
 ├── UnauthorizedError (401, UNAUTHORIZED)
 └── ForbiddenError (403, FORBIDDEN)
```

---

## 2. Esquema Universal de Respuestas de Error (Machine-Readable Contract)

Todo error devuelto por la API FastAPI cumple obligatoriamente con el contrato JSON:

```json
{
  "code": "MACHINE_READABLE_CODE",
  "message": "Mensaje legible para el usuario en español",
  "details": {
    "field": "valor_opcional"
  }
}
```

---

## 3. Contratos de Comunicación entre Capas

1. **Router $\longleftrightarrow$ Service:**
   - El Router pasa esquemas validados (DTOs) y la sesión de base de datos (`Session`) al Service.
   - El Service devuelve entidades de dominio, modelos Pydantic o levanta excepciones derivadas de `DomainError`.
   - El Router nunca maneja transacciones SQL directamente.

2. **Service $\longleftrightarrow$ Repository:**
   - El Service invoca métodos del Repository con parámetros atómicos o DTOs.
   - El Repository ejecuta queries SQLAlchemy y devuelve modelos ORM o colecciones.
   - El Repository nunca levanta excepciones HTTP ni formatea JSON.
