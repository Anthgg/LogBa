# Paquete Documental de Compras (Fase 015)

## 1. Visión General y Arquitectura

La **Fase 015 (F015_PURCHASING_DOCUMENTS)** establece el catálogo, esquemas, plantillas HTML/CSS y motor de renderizado PDF para los seis documentos canónicos del ciclo de adquisiciones y compras del Sistema Logístico Integral:

1. **Requerimiento de Compra (`REQ`)** — Plantilla `purchase_requisition_v1` (A4 Portrait)
2. **Solicitud de Cotización (`RFQ`)** — Plantilla `request_for_quotation_v1` (A4 Portrait)
3. **Cuadro Comparativo de Ofertas (`CMP`)** — Plantilla `comparative_table_v1` (A4 Landscape)
4. **Orden de Compra Oficial (`PO`)** — Plantilla `purchase_order_v1` (A4 Portrait)
5. **Acta / Aprobación de Compra (`POA`)** — Plantilla `purchase_approval_v1` (A4 Portrait)
6. **Constancia de Envío al Proveedor (`PSC`)** — Plantilla `supplier_send_confirmation_v1` (A4 Portrait)

---

## 2. Matriz Canónica de Plantillas de Compras

| Tipo Documental | Código | Ámbito | Orientación | Plantilla Clave | Versión | Estado Catálogo |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Requerimiento de Compra | `REQ` | INTERNAL | Portrait | `purchase_requisition_v1` | v1 | `DRAFT`, `PENDING`, `APPROVED`, `REJECTED`, `COMPLETED`, `VOID` |
| Solicitud de Cotización | `RFQ` | INTERNAL | Portrait | `request_for_quotation_v1` | v1 | `DRAFT`, `ISSUED`, `CLOSED`, `VOID` |
| Cuadro Comparativo de Ofertas | `CMP` | INTERNAL | **Landscape** | `comparative_table_v1` | v1 | `DRAFT`, `PENDING`, `APPROVED`, `VOID` |
| Orden de Compra Oficial | `PO` | INTERNAL | Portrait | `purchase_order_v1` | v1/v9 | `DRAFT`, `PENDING`, `APPROVED`, `ISSUED`, `COMPLETED`, `VOID` |
| Acta de Aprobación de Compra | `POA` | INTERNAL | Portrait | `purchase_approval_v1` | v1 | `PENDING`, `APPROVED`, `REJECTED` |
| Constancia de Envío a Proveedor | `PSC` | EXTERNAL | Portrait | `supplier_send_confirmation_v1` | v1 | `REGISTERED`, `PROCESSED`, `VOID` |

- **Colisiones de Código:** `PURCHASING_DOCUMENT_CODE_COLLISIONS = 0`.
- **Deuda de Catálogo:** `F011_CATALOG_DEBT = NONE` (los 6 tipos existen y están sincronizados en PostgreSQL).

---

## 3. Principios de Seguridad y Reglas de Oro

1. **Autoridad Backend Absoluta:**
   - El backend resuelve las versiones, valida esquemas Pydantic, calcula el `SNAPSHOT_HASH` (SHA-256 canónico), genera el código QR (Base64 PNG Data-URI), compila el PDF mediante WeasyPrint 69.0 y calcula el `PDF_HASH` (SHA-256).
   - En el frontend: `FRONTEND_PDF_GENERATION = 0`, `FRONTEND_QR_GENERATION = 0`, `FRONTEND_PURCHASING_CALCULATIONS = 0`.
2. **Aislamiento de Series y Correlativos:**
   - La generación de vistas previas documentales **no consume correlativos** de la Fase 013 (`PREVIEW_CONSUMES_CORRELATIVE = false`, `PURCHASING_PREVIEW_SERIES_RESERVATIONS = 0`).
   - Los previews utilizan códigos identificadores claros como `PREVIEW-REQ-LIM-2026-0001` y marcas de agua visibles (`VISTA PREVIA`, `BORRADOR` o `ANULADO`).
3. **Frontera Funcional (Ownership F031–F035):**
   - F015 implementa el motor de presentación visual y esquemas documentales.
   - La creación transaccional de requerimientos operativos pertenece a **F031**.
   - El envío y recepción de cotizaciones pertenece a **F032**.
   - La evaluación ponderada y algoritmos de selección de proveedor pertenecen a **F033**.
   - La emisión y control de entregas de OC pertenecen a **F034**.
   - El flujo jerárquico de aprobaciones por montos pertenece a **F035**.

---

## 4. Endpoints de la API

- `GET /api/logistics/document-renderer/templates?family=purchasing`: Lista las 6 plantillas de compras registradas y sus manifiestos.
- `GET /api/logistics/document-renderer/templates/{template_key}`: Obtiene el manifiesto detallado de una plantilla.
- `POST /api/logistics/document-renderer/purchasing/{doc_code}/sample?scenario=basic|multipage|long_text&format=pdf|html`: Genera una muestra de vista previa en PDF o HTML para cualquiera de los seis documentos de compras.
