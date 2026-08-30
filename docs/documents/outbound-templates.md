# Paquete Documental de Salida y Despacho (F018)

## 1. Visión General y Objetivos
La **Fase 018 (F018_OUTBOUND_DOCUMENTS)** formaliza el paquete de siete tipos/plantillas documentales oficiales para la administración física, preparación de pedidos, recolección en estanterías (picking), consolidación en bultos (packing), manifiestos de carga, actas oficiales de despacho y control de precintos de seguridad del **Sistema Logístico Integral**.

Cada plantilla opera mediante renderizado server-side WeasyPrint 69.0 sobre Jinja2, verificación criptográfica SHA-256 Dual-Stage (Snapshot Hash + PDF Hash), códigos QR técnicos decodificables y trazabilidad inmutable.

---

## 2. Matriz Canónica de Documentos de Salida (F018)

| N° | Código Canónico | Nombre del Documento | Formato / Hoja | Clave Plantilla | Aliases Registrados | Ámbito | Propósito Operativo Principal |
|---|---|---|---|---|---|---|---|
| 1 | `OUT_REQ` | Solicitud de Salida de Almacén | A4 Portrait | `outbound_request_v1` | `PED`, `OUT_REQ`, `outbound_request_v1` | `INTERNAL` | Pedido formal comercial/interno de egreso |
| 2 | `ODS` | Orden de Salida / Despacho | A4 Portrait | `outbound_order_v1` | `ODS`, `OUT_ORD`, `outbound_order_v1` | `INTERNAL` | Instrucción formal de preparación y despacho |
| 3 | `PICK` | Hoja / Lista de Picking | A4 Portrait | `picking_list_v1` | `PICK`, `picking_sheet_v1`, `picking_list_v1` | `INTERNAL` | Ruta ordenada de recolección en estantes WMS |
| 4 | `PACK` | Lista de Empaque / Packing List | A4 Portrait | `packing_list_v1` | `PACK`, `packing_list_v1` | `INTERNAL` | Detalle de bultos, pesos, dimensiones y SSCC |
| 5 | `MNF` | Manifiesto de Carga Consolidado | A4 Portrait | `manifest_v1` | `MNF`, `MAN`, `cargo_manifest_v1`, `manifest_v1` | `INTERNAL` | Consolidado de pedidos, vehículo y transportista |
| 6 | `DSP` | Guía / Acta Oficial de Despacho | A4 Portrait | `dispatch_report_v1` | `DSP`, `ADSP`, `dispatch_guide_v1`, `dispatch_report_v1` | `INTERNAL` | Constancia oficial de salida física y custodia |
| 7 | `SEAL` | Acta de Control de Precintos | A4 Portrait | `seal_control_v1` | `SEAL`, `CPREC`, `seal_control_v1` | `INTERNAL` | Registro de precintos de seguridad y eventos de reemplazo |

---

## 3. Fronteras Funcionales Estrictas y Fases Propietarias

La Fase F018 diseña y compila **exclusivamente contratos documentales y vistas previas server-side**:
- `F018_STOCK_MUTATIONS = 0`
- `F018_STOCK_RESERVATIONS = 0`
- `F018_PICKING_MUTATIONS = 0`
- `F018_PACKING_MUTATIONS = 0`
- `F018_DISPATCH_MUTATIONS = 0`
- `F018_SEAL_MUTATIONS = 0`
- `PREVIEW_CONSUMES_CORRELATIVE = false`
- `OUTBOUND_PREVIEW_SERIES_RESERVATIONS = 0`
- `FRONTEND_STOCK_CALCULATIONS = 0`, `FRONTEND_PDF_GENERATION = 0`, `FRONTEND_QR_GENERATION = 0`

### Mapeo de Fases Futuras del Plan Maestro:
- **F051 (Pedidos de Salida):** Gestión operativa de pedidos de clientes y transferencias de salida.
- **F052 (Reserva de Stock):** Asignación y reserva determinista FIFO/FEFO en base de datos.
- **F053 (Picking Operativo):** Creación de olas de picking, asignación de tareas a operadores y confirmación por escáner.
- **F054 (Packing Operativo):** Estaciones de empaque, generación de etiquetas SSCC y pesaje de bultos.
- **F055 (Planificación de Despacho):** Asignación de muelles de carga, consolidación de rutas y ventanas horarias.
- **F056 (Emisión de ODS):** Generación operacional de órdenes de salida vinculadas a series y talonarios.
- **F057 (Liberación de Despacho):** Autorización de alto riesgo mediante Step-Up MFA TOTP.
- **F058 (Carga y Precintos):** Registro físico de estiba, pesaje en balanza y colocación de precintos.
- **F059 (Paquete Documental de Viaje):** Compilación consolidada de guías, manifiestos y hojas de ruta.
- **F060 (Reimpresión y Contingencia):** Gestión de anulaciones y reimpresiones con auditoría.

---

## 4. Endpoints y Seguridad RBAC

### Endpoint Canónico:
`POST /api/logistics/document-renderer/outbound/{doc_code}/sample`

- **Permiso Requerido:** `document_templates.preview`
- **Parámetros:**
  - `doc_code`: Código del documento (`OUT_REQ`, `ODS`, `PICK`, `PACK`, `MNF`, `DSP`, `SEAL`).
  - `scenario`: Escenario sintético (`basic`, `multipage`, `high_priority`, `multi_package`, `with_difference`, `replacement`).
  - `format`: Formato de salida (`pdf` o `html`).
  - `status_code`: Estado documental opcional.

---

## 5. Pruebas de Calidad y Verificación
- **Pytest:** `tests/test_outbound_templates_flow.py` (12/12 pruebas PASSED).
- **Cobertura Total de Plantillas:** 50/50 pruebas PASSED (F015, F016, F017, F018).
- **Linter & Formatter:** `ruff check .` (100% limpio), `ruff format --check .` (171 archivos limpios).
- **Tipado Estático:** `mypy app` (108 archivos limpios, 0 errores).
- **Migraciones:** `alembic heads` -> `0009_f014 (head)` (NO_SCHEMA_CHANGE).
