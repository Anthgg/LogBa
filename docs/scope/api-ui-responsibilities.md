# Matriz de Responsabilidades API ↔ UI y Políticas de Contrato

Este documento formaliza la **Regla de Oro Transversal** del proyecto, define la matriz canónica de responsabilidades entre capas y establece las políticas estrictas de control de errores, validaciones y datos reales.

---

## 1. Regla de Oro Transversal (F001 — F100)

> **EL BACKEND HACE TODO EL TRABAJO DE NEGOCIO.**
> **EL FRONTEND ES EXCLUSIVAMENTE UNA CAPA DE PRESENTACIÓN E INTERACCIÓN.**

```text
EL FRONTEND PIDE.
   ↓
EL BACKEND RECIBE.
   ↓
EL BACKEND VALIDA.
   ↓
EL BACKEND DECIDE.
   ↓
EL BACKEND CONSULTA.
   ↓
EL BACKEND CALCULA.
   ↓
EL BACKEND GENERA.
   ↓
EL BACKEND PERSISTE.
   ↓
EL BACKEND RESPONDE.
   ↓
EL FRONTEND PRESENTA.
```

---

## 2. Matriz Canónica de Responsabilidades

| Capacidad del Sistema | Backend (FastAPI) | Frontend (React + Vite) | Descripción de Autoridad |
| :--- | :---: | :---: | :--- |
| **Conexión PostgreSQL / Supabase** | **YES (Único)** | **NO** | Conexión directa desde frontend prohibida (`DIRECT_DATABASE_ACCESS_FROM_FRONTEND=0`). |
| **Ejecución de Consultas SQL** | **YES** | **NO** | Solo el backend ejecuta consultas mediante SQLAlchemy. |
| **Transacciones de Negocio** | **YES** | **NO** | Control de commits, rollbacks y niveles de aislamiento en backend. |
| **Reglas Logísticas y Estados** | **YES** | **NO** | Validaciones de stock, bloqueos y transiciones de estado oficiales. |
| **Cálculos y Fórmulas** | **YES** | **NO** | Subtotales, impuestos (IGV), descuentos, cubicajes y kardex calculados en backend. |
| **Generación Oficial de PDF** | **YES** | **NO** | Generación binaria vectorial de documentos oficiales; frontend solo descarga o muestra. |
| **Generación Oficial de Excel/CSV**| **YES** | **NO** | Generación y streaming de archivos estructurados desde backend. |
| **Consumo de APIs Externas** | **YES** | **NO** | RUC, DNI, placas, geocodificación y ruteo orquestados exclusivamente por backend. |
| **Secretos y Claves Privadas** | **YES** | **NO** | Credenciales de DB, service_role y API keys prohibidas en frontend (`FRONTEND_SECRET_KEYS=0`). |
| **Autoridad de Permisos (RBAC)** | **YES** | **NO** | Backend valida identidad, rol, organización, sede y almacén en cada solicitud. |
| **Presentación y Renderizado UI** | **NO (Envía JSON/Data)**| **YES** | Renderizado de tablas, dashboards, botones, modales y navegación visual. |
| **Formularios de Captura** | **Valida Autoridad** | **Captura y Envío** | Frontend valida formato básico para UX; Backend revalida el 100% de los datos. |
| **Navegación y Rutas de Pantalla**| **NO** | **YES** | Manejo del enrutamiento de vistas y estado puramente visual en cliente. |

---

## 3. Política de Prerrequisitos Operativos

Una operación de negocio **nunca** debe fallar con un error no controlado (`500 Internal Server Error`) cuando faltan dependencias operativas o datos maestros previos.

### Reglas de Dependencia:
1. Si una operación requiere entidades previas (por ejemplo: Recepción requiere Organización, Sede, Almacén y OC aprobada):
   - El backend valida la existencia y estado activo de todas las dependencias.
   - Si falta un prerrequisito, devuelve una respuesta HTTP `409 Conflict` o `422 Unprocessable Entity` con estructura controlada.
2. Formato estandarizado de respuesta de prerrequisito:
   ```json
   {
     "code": "WAREHOUSE_LOCATION_REQUIRED",
     "message": "La sede seleccionada no cuenta con un almacén activo asignado para recepción.",
     "details": {
       "branch_id": "br_12345",
       "missing_entity": "warehouse"
     }
   }
   ```

---

## 4. Política de Códigos de Error Estables (Machine-Readable Error Contract)

El frontend nunca debe tomar decisiones de flujo basadas en la comparación de cadenas de texto de mensajes humanos (`message`), ya que los textos pueden cambiar por internacionalización o redacción.

### Estructura Universal de Error:
```json
{
  "code": "STABLE_SNAKE_CASE_CODE",
  "message": "Texto descriptivo en español para visualización amigable al usuario.",
  "details": {
    "field": "quantity",
    "constraint": "AVAILABLE_STOCK_EXCEEDED",
    "requested": 50,
    "available": 32
  }
}
```

- **`code`:** Código de error estático y tipado para manejo programático en frontend.
- **`message`:** Mensaje redactado para presentación visual directa en alertas de UI.
- **`details`:** Metadatos estructurados para destacar campos específicos en formularios.

---

## 5. Política de Datos Reales en Producción (Anti-Mocking Rule)

```text
FAKE_OPERATIONAL_DATA_IN_PRODUCTION = FORBIDDEN
MOCKED_OPERATIONAL_ACTIONS = 0
STUBBED_OPERATIONAL_ACTIONS = 0
```

1. **Entorno Productivo:** Prohibido el uso de fixtures falsos, coordenadas inventadas, polilíneas simuladas o respuestas hardcodeadas que sustituyan una operación real de backend.
2. **Entorno de Pruebas Unitarias:** Los mocks están permitidos **únicamente** en suites de tests aisladas (ej. `pytest` en CI sin DB real) para comprobar lógica de componentes, pero nunca en el código de producción.

---

## 6. Clasificación Canónica de Contratos de Endpoints

Cada endpoint backend implementado a lo largo de las 100 fases debe pertenecer obligatoriamente a una de las siguientes categorías:

1. **`UI_INTEGRATED`:** Endpoint consumido activamente por una vista o componente del frontend.
2. **`API_ONLY_JUSTIFIED`:** Endpoint diseñado para integración programática externa o automatizaciones M2M explícitamente justificadas.
3. **`INTERNAL_ONLY`:** Servicios internos orquestados entre componentes del backend.
4. **`SYSTEM_AUTOMATION`:** Probes de infraestructura, health checks (`/live`, `/ready`) o pipelines de mantenimiento.
5. **`FUTURE_PHASE_OWNER`:** Endpoints reservados y asignados formalmente a fases posteriores.
