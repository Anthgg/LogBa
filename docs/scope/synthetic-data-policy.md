# Política Canónica de Datos Sintéticos Realistas (Segunda Regla de Oro)

Esta directriz es de cumplimiento estricto y transversal en todo el ciclo de desarrollo del **Sistema Logístico Integral (F001 — F100)**.

---

## 1. Principio Fundamental

> **DATOS FALSOS:** SÍ, PARA PRUEBAS Y DEMOSTRACIÓN.  
> **FLUJOS FALSOS:** NUNCA.  
> **BACKEND FALSO:** NUNCA.  
> **BASE DE DATOS FALSA:** NUNCA.  
> **RESPUESTAS HARDCODEADAS EN FRONTEND:** PROHIBIDAS.  
> **DATOS SINTÉTICOS EN PRODUCCIÓN:** NUNCA (`FAKE_OPERATIONAL_DATA_IN_PRODUCTION = 0`).

---

## 2. Diferencia Crítica: Mock vs. Dato Sintético

| Concepto | Definición | Uso en el Proyecto |
| :--- | :--- | :---: |
| **MOCK (Prohibido)** | Respuesta simulada o array hardcodeado en frontend (`const clientes = [...]`) que elude la ejecución de la arquitectura real. | **PROHIBIDO** para validación operativa o demostración de módulos. |
| **DATO SINTÉTICO (Obligatorio)** | Registro ficticio realista inyectado mediante seeds/servicios del backend que atraviesa **Backend $\rightarrow$ PostgreSQL $\rightarrow$ API FastAPI $\rightarrow$ Frontend UI**. | **OBLIGATORIO** para cada módulo funcional. |

---

## 3. Escenarios Realistas Requeridos por Módulo

Cada módulo funcional debe probarse no solo con el "camino feliz", sino con un espectro completo de situaciones operativas:

1. **Caso Normal (Happy Path):** Operación estándar con todos los datos conformes.
2. **Caso Parcial:** Recepciones parciales con faltantes, entregas parciales con ítems no conformes.
3. **Caso de Rechazo:** Entrega rechazada en destino con motivo tipificado, recepción rechazada por daño.
4. **Caso de Conflicto:** Quiebre de stock al intentar reservar, coincidencia de placa en garita sin cita.
5. **Dependencias Faltantes:** Intento de recepción sin almacén activo (retornando `409 Conflict` estructurado).
6. **Casos Límite (Edge Cases):** Cantidades cero, valores monetarios altos, textos/nombres extensos, paginación masiva.

---

## 4. Control de Entornos y Protección de Producción

Los datos sintéticos solo están autorizados en entornos controlados de desarrollo, testing y staging:

- **`development`:** PERMITIDO
- **`test`:** PERMITIDO
- **`staging`:** PERMITIDO
- **`production`:** **ESTRICTAMENTE PROHIBIDO**

### Mecanismo de Bloqueo de Seeds en Producción:
Todo script de generación o seeding de datos sintéticos debe incluir una cláusula explícita e intransigente de protección:
```python
if settings.is_production or settings.APP_ENV.lower() == "production":
    raise RuntimeError(
        "CRITICAL ERROR: Synthetic demo data cannot be seeded in PRODUCTION environment."
    )
```

---

## 5. Gate de Calidad Obligatorio en Fases Funcionales

A partir de la primera fase que implemente modelos de datos de negocio, el reporte de cierre debe certificar:

```text
SYNTHETIC_TEST_DATA_CREATED=PASS/NOT_APPLICABLE
REALISTIC_HAPPY_PATH=PASS/NOT_APPLICABLE
REALISTIC_ERROR_CASES=PASS/NOT_APPLICABLE
BACKEND_SEEDED_DATA=PASS/NOT_APPLICABLE
DATA_PERSISTED_IN_REAL_POSTGRES=PASS/NOT_APPLICABLE
FRONTEND_RENDERED_BACKEND_DATA=PASS/NOT_APPLICABLE
HARDCODED_OPERATIONAL_FRONTEND_DATA=0
FAKE_OPERATIONAL_DATA_IN_PRODUCTION=0
PRODUCTION_SEED_PROTECTION=PASS/NOT_APPLICABLE
```
