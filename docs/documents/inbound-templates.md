# Paquete Documental de Ingreso y Recepción (Fase 016)

## 1. Visión General y Objetivos
La **Fase 016 (F016_INBOUND_DOCUMENTS)** establece el estándar documental canónico para el ciclo de ingreso de mercancías y recepción en almacenes del **Sistema Logístico Integral**. Diseña e implementa las 6 plantillas de documentos oficiales, esquemas de datos Pydantic, renderizado server-side WeasyPrint 69.0, hashes inmutables SHA-256 y códigos QR de verificación técnica.

---

## 2. Catálogo Canónico de Documentos de Ingreso

| Código | Nombre Canónico | Familia | Ámbito | Clave Plantilla | Versión | Formato |
|---|---|---|---|---|---|---|
| `ARR` | Cita de Llegada / Arribo | `RECEIVING` | `INTERNAL` | `arrival_appointment_v1` | v1 | A4 Portrait |
| `CPV` | Control de Puerta Vehicular | `RECEIVING` | `INTERNAL` | `gate_control_v1` | v1 | A4 Portrait |
| `REC` | Acta de Recepción Técnica | `RECEIVING` | `INTERNAL` | `receiving_report_v1` | v1 | A4 Portrait |
| `GRN` | Guía de Ingreso a Almacén | `RECEIVING` | `INTERNAL` | `goods_receipt_v1` | v1 | A4 Portrait |
| `RDIFF` | Acta de Diferencias de Recepción | `RECEIVING` | `INTERNAL` | `receiving_difference_v1` | v1 | A4 Portrait |
| `NC` | Reporte de No Conformidad | `RECEIVING` | `INTERNAL` | `non_conformity_v1` | v1 | A4 Portrait |

---

## 3. Especificación Técnica de las Plantillas

### 3.1 Cita de Llegada / Arribo (`ARR` - `arrival_appointment_v1`)
- **Propósito:** Certificar la asignación de ventana horaria y muelle para la descarga de unidades de transporte en patio.
- **Campos Principales:** Ventana de llegada, muelle asignado, transportista, conductor, placa de tracto/carreta, orden de compra asociada, total de bultos/pallets y peso estimado.
- **Estados Soportados:** `SCHEDULED`, `CHECKED_IN`, `UNLOADED`, `CANCELLED`.

### 3.2 Control de Puerta Vehicular (`CPV` - `gate_control_v1`)
- **Propósito:** Registro formal de inspección de seguridad en garita vehicular a la entrada y salida de las instalaciones.
- **Campos Principales:** Hora de ingreso, hora de salida, placa, conductor (DNI/licencia), número de precinto de seguridad de origen, lista de verificación física (EPP, estado de carrocería, documentación presentada).
- **Estados Soportados:** `INSIDE`, `EXITED`, `CANCELLED`.

### 3.3 Acta de Recepción Técnica (`REC` - `receiving_report_v1`)
- **Propósito:** Documentar la inspección cuantitativa y cualitativa en muelle de descarga.
- **Campos Principales:** Comparación detallada de cantidades ordenadas vs recibidas, número de lote, fecha de vencimiento, condición de empaque, bultos muestreados y dictamen técnico (`CONFORM`, `OBSERVED`, `REJECTED`).
- **Estados Soportados:** `DRAFT`, `COMPLETED`, `VOID`.

### 3.4 Guía de Ingreso a Almacén / Nota de Ingreso (`GRN` - `goods_receipt_v1`)
- **Propósito:** Sustento documental oficial del ingreso físico y custodia de existencias en almacén.
- **Campos Principales:** Acta de recepción asociada, orden de compra, artículos con cantidades aceptadas, unidad de medida, lote asignado, ubicación física de destino (racks/pasillos) y estado de calidad.
- **Estados Soportados:** `DRAFT`, `ISSUED`, `CANCELLED`.

### 3.5 Acta de Diferencias de Recepción (`RDIFF` - `receiving_difference_v1`)
- **Propósito:** Constancia técnica inmediata de discrepancias encontradas durante la descarga física.
- **Campos Principales:** Clasificación de discrepancias (`SHORTAGE`, `EXCESS`, `DAMAGED`, `WRONG_PRODUCT`, `MISSING_DOCUMENT`, `BROKEN_SEAL`), cantidades esperadas vs recibidas, severidad, evidencia y firma conjunta del transportista y receptor.
- **Estados Soportados:** `OPEN`, `RESOLVED`, `VOID`.

### 3.6 Reporte de No Conformidad (`NC` - `non_conformity_v1`)
- **Propósito:** Formalizar afectaciones de calidad, desviaciones de especificación técnica o incumplimientos del proveedor.
- **Campos Principales:** Lote y producto afectado, hallazgos categorizados, severidad global (`LEVE`, `MODERADA`, `CRITICA`), evidencia fotográfica referenciada, propuesta de disposición técnica y plan de acción requerido.
- **Estados Soportados:** `ISSUED`, `ACCEPTED_BY_SUPPLIER`, `CLOSED`.

---

## 4. Reglas de Autoridad y Fronteras Funcionales
1. **Autoridad Backend Estricta:**
   - La generación de PDF, cálculo de hash criptográfico (SHA-256 Dual-Stage), generación del código QR y serialización del snapshot canónico se realiza exclusivamente en el backend (`LogBa`).
   - El frontend (`fronlog`) actúa como cliente de visualización y descarga (`FRONTEND_PDF_GENERATION = 0`, `FRONTEND_QR_GENERATION = 0`).
2. **Aislamiento de Series y Correlativos:**
   - Las vistas previas (`POST /api/logistics/document-renderer/receiving/{doc_code}/sample`) no consumen correlativos de series oficiales (`PREVIEW_CONSUMES_CORRELATIVE = false`, `INBOUND_PREVIEW_SERIES_RESERVATIONS = 0`).
   - Todos los documentos de prueba incluyen marcas de agua claras (`VISTA PREVIA` o `BORRADOR`).
3. **Frontera de Fases Futuras (F036 a F041+):**
   - La Fase 016 define **plantillas y contratos documentales**.
   - No implementa mutaciones de stock/inventario (`F016_INVENTORY_MUTATIONS = 0`), ni flujos operativos de control de muelle (F038), escaneo de código de barras (F039), resolución transaccional de discrepancias (F040), ni planes de calidad/scrap (F041+).
