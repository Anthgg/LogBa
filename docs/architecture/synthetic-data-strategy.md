# Estrategia de Datos Sintéticos y Escenarios de Prueba

Este documento formaliza la estrategia técnica de generación de datos sintéticos realistas en el **Sistema Logístico Integral**.

---

## 1. Arquitectura de Generación (Seeding Architecture)

Los datos sintéticos se generan exclusivamente a través de la capa de servicios del backend para garantizar que todas las invariantes y reglas de negocio se ejecuten exactamente igual que con datos reales:

```text
COMANDO DE SEED (python -m app.scripts.seed_demo)
   ↓ Valida entorno != production
DOMAIN SERVICES (app/modules/{domain}/services/...)
   ↓ Ejecuta invariantes y transacciones
POSTGRESQL (Supabase)
   ↓ Persiste entidades y Kardex
FASTAPI ENDPOINTS
   ↓ Serializa contratos JSON
FRONTEND UI
```

---

## 2. Bloqueo de Seguridad en Producción

Todo script de seeding incluye una validación obligatoria e intransigente:

```python
from app.core.config import get_settings

settings = get_settings()

if settings.is_production or settings.APP_ENV.lower() == "production":
    raise RuntimeError(
        "CRITICAL ERROR: Synthetic demo data cannot be seeded in PRODUCTION environment."
    )
```

---

## 3. Estado de la Fase F003

- **`SYNTHETIC_DATA_ARCHITECTURE`:** `PASS` (Arquitectura, políticas y bloqueo de seguridad formalizados).
- **`SYNTHETIC_TEST_DATA_CREATED`:** `NOT_APPLICABLE` (No se generan datos operativos artificiales en F003 hasta que existan los modelos de datos en F004+).
