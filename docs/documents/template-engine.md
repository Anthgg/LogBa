# Motor Central de Plantillas HTML/CSS → PDF y Renderizado Documental (Fase 014)

## 1. Arquitectura y Principio de Autoridad
El **Motor Central de Renderizado Documental** de la Plataforma Logística es la autoridad técnica y de seguridad exclusiva para la generación de documentos oficiales y vistas previas.

```
+-----------------------------------------------------------------------------------+
|                            CANONICAL BACKEND ENGINE                               |
|                                                                                   |
|  [DocumentRenderContext]                                                          |
|           |                                                                       |
|           +---> Canonical JSON Serialization (UTF-8, Sorted Keys)                 |
|           |                 |                                                     |
|           |                 v                                                     |
|           |          SNAPSHOT_HASH (SHA-256)                                      |
|           |                 |                                                     |
|           |                 +---> QR Code Generation (PNG Data URI Base64)        |
|           |                 |                                                     |
|           +-----------------+                                                     |
|           |                                                                       |
|           v                                                                       |
|  [Template Registry] ---> [Jinja2 Template Engine (Autoescape, Strict Sandbox)]  |
|                                     |                                             |
|                                     v                                             |
|                              [HTML Document]                                      |
|                                     |                                             |
|                                     v                                             |
|                      [WeasyPrint PDF Compiler (Local-Only)]                       |
|                                     |                                             |
|                                     v                                             |
|                              [PDF Byte Stream]                                    |
|                                     |                                             |
|                                     v                                             |
|                             PDF_HASH (SHA-256)                                    |
+-----------------------------------------------------------------------------------+
```

### Reglas de Autoridad y Fronteras:
- `FRONTEND_PDF_GENERATION = 0`: Ningún cliente web compila PDFs oficiales ni genera artefactos finales.
- `FRONTEND_QR_GENERATION = 0`: Los códigos QR oficiales son generados por el backend e integrados en el flujo de renderizado.
- `FRONTEND_DOCUMENT_HASH_AUTHORITY = 0`: La integridad criptográfica del documento se basa en hashes SHA-256 calculados por el backend.

---

## 2. Estrategia de Dos Etapas de Hasheo Criptográfico (SHA-256)

Para evitar la ambigüedad circular en la que un PDF debe contener un código QR con su propio hash antes de ser compilado, se implementó una estrategia canónica en dos etapas:

1. **`SNAPSHOT_HASH` (Etapa Pre-Render)**:
   - Se serializa el contexto de renderizado a un JSON canónico determinista (claves ordenadas, separadores compactos `,:` sin espacios, codificación UTF-8).
   - Se calcula el `SNAPSHOT_HASH = SHA-256(canonical_snapshot_json)`.
   - Este hash se incluye dentro de la metadata del código QR y en el pie de página del documento para verificación técnica inmediata.
2. **`PDF_HASH` (Etapa Post-Render)**:
   - Tras compilar el archivo PDF con WeasyPrint, se calcula el `PDF_HASH = SHA-256(pdf_bytes)`.
   - Este hash certifica la integridad exacta del binario generado y se asocia a la entidad `document_render_artifacts`.

---

## 3. Seguridad y Controles de Mitigación

1. **Protección contra Server-Side Request Forgery (`PDF_RENDERER_SSRF = 0`)**:
   - WeasyPrint utiliza un `local_only_url_fetcher` que rechaza de inmediato cualquier esquema `http://`, `https://` o `ftp://`, impidiendo el escaneo de redes internas o el acceso a endpoints de metadata de Cloud (`169.254.169.254`).
2. **Protección contra Path Traversal (`TEMPLATE_PATH_TRAVERSAL = 0`)**:
   - `TemplateRegistry` mapea claves inmutables autorizadas (ej. `base_document_v1`) a rutas internas dentro de la raíz de plantillas. Se rechaza cualquier clave que contenga `..`, `/` o `\`.
3. **Protección contra Template Injection (`TEMPLATE_INJECTION_PROTECTION = PASS`)**:
   - Jinja2 opera con `autoescape=True` y `StrictUndefined`. Los datos del usuario se tratan estrictamente como cadenas de texto sanitizadas, sin uso de `|safe` en entradas de usuario ni ejecución arbitraria.
4. **Dependencias de Recursos Remotos (`REMOTE_TEMPLATE_DEPENDENCIES = 0`)**:
   - No se emplean Google Fonts externas, CDNs ni recursos externos. La tipografía estándar utiliza fuentes locales del contenedor (`Liberation Sans`, `DejaVu Sans`).

---

## 4. Estándar de Plantilla Base (`base_document_v1`)

La primera plantilla canónica implementa:
- **Formato A4** con márgenes estándar y CSS `@page`.
- **Encabezado Institucional**: Nombre de organización, RUC/Tax ID, sede emisora, dirección física, logotipo institucional opcional.
- **Identificación Documental**: Nombre del tipo documental, código canónico oficial (`TIPO-SEDE-AÑO-CORRELATIVO`), estado del documento (`DRAFT`, `APPROVED`, `ISSUED`, `VOID`), número de versión.
- **Grilla de Metadata**: Parámetros clave estructurados (proveedor, condición de pago, moneda, etc.).
- **Tablas Paginadas**: Repetición automática de encabezados de tabla en saltos de página (`thead { display: table-header-group; }`).
- **Notas y Observaciones**: Bloque de notas con soporte de caracteres especiales y Unicode.
- **Bloque de Verificación QR**: Imagen PNG en base64 con payload estructurado y `SNAPSHOT_HASH`.
- **Firma Visual (`VISUAL_SIGNATURE_ONLY = TRUE`)**: Bloque de firma con nombre, cargo y fecha del responsable (sin declarar firma digital legal o certificado PKI si no aplica).
- **Paginación Dinámica**: Numeración en pie de página mediante contadores CSS `counter(page)` de `counter(pages)`.

---

## 5. Asignación de Plantillas y Fases Futuras

El Catálogo Documental (F011) asocia cada versión documental con una plantilla mediante `template_key`.

| Familia Documental | Fase Propietaria | Estado en F014 |
| :--- | :--- | :--- |
| **Base / Universal** | **F014** | `base_document_v1` (Disponible) |
| **Compras (Purchasing)** | **F015** | `FUTURE_PHASE_OWNER_F015` |
| **Ingreso / Recepción (Receiving)** | **F016** | `FUTURE_PHASE_OWNER_F016` |
| **Inventario (Inventory)** | **F017** | `FUTURE_PHASE_OWNER_F017` |
| **Salida / Despacho (Outbound)** | **F018** | `FUTURE_PHASE_OWNER_F018` |
| **Transporte y Entrega (Transport)** | **F019** | `FUTURE_PHASE_OWNER_F019` |
| **Centro Documental / Archivo** | **F020** | `FUTURE_PHASE_OWNER_F020` |
