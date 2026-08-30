# Paquete Documental de Inventario y Almacén (F017)

## 1. Visión General
La **Fase 017 (F017_INVENTORY_DOCUMENTS)** formaliza los siete documentos oficiales para la gestión física y de control de existencias del **Sistema Logístico Integral**. Cada documento se encuentra respaldado por esquemas Pydantic deterministas, plantillas Jinja2 con renderizado server-side WeasyPrint 69.0, hashes criptográficos SHA-256 (Dual-Stage) y códigos QR para trazabilidad inmutable.

---

## 2. Matriz de Documentos de Inventario

| N° | Código Canónico | Nombre del Documento | Familia | Ámbito | Clave Plantilla | Aliases | Formato de Salida |
|---|---|---|---|---|---|---|---|
| 1 | `LBL` | Etiqueta de Ubicación / Pallet | `INVENTORY` | `INTERNAL` | `location_label_v1` | `location_label_v1` | 100x150mm (Térmica / Label) |
| 2 | `MOV` | Movimiento Interno de Inventario | `INVENTORY` | `INTERNAL` | `inventory_movement_v1` | `inventory_movement_v1` | A4 Portrait |
| 3 | `INV_ADJ` | Ajuste de Inventario | `INVENTORY` | `INTERNAL` | `inventory_adjustment_v1` | `ADJ`, `inventory_adjustment_v1` | A4 Portrait |
| 4 | `CNT` | Conteo Físico / Inventario Cíclico | `INVENTORY` | `INTERNAL` | `physical_count_v1` | `stock_count_v1` | A4 Portrait |
| 5 | `CDIFF` | Diferencia de Conteo Físico | `INVENTORY` | `INTERNAL` | `count_difference_v1` | `count_difference_v1` | A4 Portrait |
| 6 | `TRF` | Solicitud de Transferencia entre Almacenes | `INVENTORY` | `INTERNAL` | `warehouse_transfer_v1` | `transfer_request_v1` | A4 Portrait |
| 7 | `TRF_REC` | Recepción de Transferencia | `INVENTORY` | `INTERNAL` | `transfer_receipt_v1` | `TREC`, `transfer_receipt_v1` | A4 Portrait |

---

## 3. Especificaciones y Características Clave

### 3.1 Etiqueta de Ubicación WMS (`LBL`)
- **Propósito:** Identificación física en estanterías, racks, pasillos y pallets.
- **Formato:** Hoja compacta de 100mm x 150mm diseñada para impresión en impresoras térmicas e industriales.
- **Jerarquía:** Zona, Pasillo, Rack, Nivel, Posición y Código Canónico de Ubicación (ej. `ALM01-SECTOR-A-P01-R02-N03`).
- **QR:** Código QR de alta densidad con payload JSON conteniendo `document_type`, `display_code`, `snapshot_hash` y metadatos.

### 3.2 Movimiento Interno de Inventario (`MOV`)
- **Propósito:** Registro de reubicación física de stock (slotting/cross-docking) entre ubicaciones del mismo almacén.
- **Trazabilidad:** Posición de origen, posición de destino, lote, SKU, motivo y firma del operador.

### 3.3 Ajuste de Inventario (`INV_ADJ`)
- **Propósito:** Regularización formal de existencias por merma, rotura, desmedro o sobrante.
- **Estructura:** Comparativa de cantidades *Antes*, *Ajuste (Delta)* y *Después*, costo unitario e impacto valorizado total en moneda local.
- **Seguridad:** Requiere validación Step-Up (MFA) para operaciones de alto riesgo según directiva F009.

### 3.4 Conteo Físico / Inventario Cíclico (`CNT`)
- **Propósito:** Planilla de toma física para cuadrillas de inventario por zonas o barrido total (*wall-to-wall*).
- **Modo Conteo Ciego (Blind Count):** Cuando `blind_count=True`, el backend omite completamente el campo `system_qty` (saldo teórico) del contexto para garantizar la total independencia y objetividad de la auditoría física (`BLIND_COUNT_DOCUMENT_SUPPORT = PASS`).

### 3.5 Diferencia de Conteo Físico (`CDIFF`)
- **Propósito:** Balance comparativo entre stock teórico del sistema y conteo físico real.
- **Estructura:** Clasificación de discrepancias (*Faltante / Sobrante*), análisis de causa raíz y firmas de conformidad y control interno.

### 3.6 Solicitud de Transferencia entre Almacenes (`TRF`)
- **Propósito:** Orden de traspaso de existencias entre dos almacenes o sucursales de la empresa.
- **Trazabilidad:** Almacén origen, almacén destino, fecha límite de arribo, transportista, placa y detalle de bultos/lotes.

### 3.7 Recepción de Transferencia (`TRF_REC`)
- **Propósito:** Acta de conformidad y verificación de llegada en el almacén de destino.
- **Estructura:** Confrontación de cantidades despachadas vs cantidades efectivamente recibidas, detección de faltantes o daños en tránsito y observaciones de custodia.

---

## 4. Fronteras Funcionales y Futuro Ownership
Fase F017 implementa exclusivamente el **diseño, renderizado y descarga documental**.

- `F017_INVENTORY_MUTATIONS = 0`
- `F017_STOCK_ADJUSTMENT_MUTATIONS = 0`
- `F017_TRANSFER_STOCK_MUTATIONS = 0`
- `PREVIEW_CONSUMES_CORRELATIVE = false`
- `INVENTORY_PREVIEW_SERIES_RESERVATIONS = 0`

**Responsabilidades de Fases Futuras:**
- **F022:** Maestros de almacén y ubicaciones físicas operativas
- **F023:** Maestro de productos y catálogo de materiales
- **F024:** Conversión de unidades de medida (UOM)
- **F044:** Kardex / Libro diario de movimientos de inventario
- **F045:** Saldos de stock en tiempo real
- **F046:** Gestión de lotes, series de producto y unidades logísticas
- **F047:** Flujo operativo y aprobación de ajustes de inventario
- **F048:** Flujo operativo de conteos físicos y conciliación de diferencias
- **F049:** Flujo operativo de despachos de transferencias inter-almacenes
- **F050:** Flujo operativo de recepción y cierre de transferencias

---

## 5. Endpoints REST API

### Generar Muestra / Vista Previa de Documento de Inventario
- **Ruta:** `POST /api/logistics/document-renderer/inventory/{doc_code}/sample`
- **Permiso Requerido:** `document_templates.preview`
- **Parámetros:**
  - `doc_code`: `LBL`, `MOV`, `INV_ADJ` (o `ADJ`), `CNT`, `CDIFF`, `TRF`, `TRF_REC` (o `TREC`)
  - `scenario`: `basic`, `blind`, `multipage`, `long_text`, `difference`
  - `format`: `pdf` (por defecto) o `html`
- **Headers Retornados:**
  - `X-Snapshot-Hash`: Hash SHA-256 canónico del contexto de datos.
  - `X-Pdf-Hash`: Hash SHA-256 del archivo binario PDF emitido.
  - `X-Template-Key`: Clave de la plantilla utilizada.
  - `X-Document-Type`: Código canónico del documento.
  - `X-Renderer-Name`: `WeasyPrint`
  - `X-Renderer-Version`: `69.0`
