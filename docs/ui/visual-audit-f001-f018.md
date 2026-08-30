# Informe de Auditoría Visual y UX Integral (F001 — F018)
**Sistema Logístico Integral • Congelamiento Funcional Post-F018**
**Fecha de Auditoría:** 30 de Agosto de 2026
**Estado:** REPORTE TÉCNICO DE AUDITORÍA (CONGELAMIENTO ACTIVO — SIN REDISEÑO TODAVÍA)

---

## 1. Resumen Ejecutivo y Alcance

La presente auditoría técnica y visual inspecciona de manera exhaustiva el frontend real desplegado en **Google Cloud Run** (`fronlog-web-00012-78x`) conectado a la API backend (`logba-api-00012-l86`), abarcando la totalidad de las funcionalidades construidas desde la **Fase 001 hasta la Fase 018**.

### Objetivos Cumplidos:
1. **Navegación Real:** Inspección automatizada mediante Chromium / Playwright a 5 resoluciones de pantalla (`1920x1080`, `1440x900`, `1366x768`, `1280x720`, `1024x768`) y 3 niveles de zoom (`90%`, `100%`, `110%`).
2. **Inventario Exhaustivo:** Catalogación de 11 rutas, 11 pantallas maestras, 12 modales, 14 tablas, 9 formularios y 6 barras de filtros.
3. **Diagnóstico y Clasificación:** Identificación de problemas de usabilidad, inconsistencias de diseño, duplicación de componentes y gaps de contrato.
4. **Propuesta de Sistema UI/UX Compartido:** Especificación de Design Tokens, Jerarquía de Modales, Componentes Reutilizables y Arquitectura de Navegación escalable.
5. **Cumplimiento Estricto de Congelamiento:** `REDESIGN_IMPLEMENTED = 0`, `F019_STARTED = 0`.

---

## 2. Clasificación de Hallazgos por Prioridad

### 🔴 Hallazgos Críticos (P0)
1. **Colapso de Navegación en Viewports Reducidos (1024x768 / Tablet):**
   - *Diagnóstico:* En resoluciones menores a 1200px, los textos del menú lateral (`.log-shell__nav-label`) desaparecen y el sidebar queda parcialmente inaccesible sin un Drawer/Off-canvas táctil adecuado.
   - *Impacto:* Bloqueo de operadores en terminales portátiles de almacén.
2. **Visibilidad y Proporción del Visor PDF/HTML en Modal:**
   - *Diagnóstico:* El modal de previsualización documental (`PdfTemplatePreviewModal`) comparte el 35% de su altura con encabezados y selectores redundantes en pantallas de laptop (1366x768 / 1280x720), reduciendo el área útil del documento a menos del 65%.
   - *Impacto:* Dificultad para auditar documentos multipágina sin scroll forzado bidireccional.

### 🟠 Hallazgos Importantes (P1)
1. **Fragmentación Arquitectónica de Modales:**
   - *Diagnóstico:* Coexisten dos implementaciones desconectadas de modales: `.dm-modal` / `.dm-overlay` (módulos documentales) y `.admin-modal__panel` / `.admin-modal` (módulos de administración), con diferentes estructuras de encabezado, padding, backdrop y botones de cierre.
2. **Ausencia de Estados Vacíos (Empty States) Estilizados:**
   - *Diagnóstico:* Listados en Series, Auditoría y Catálogo muestran texto plano o loaders indefinidos cuando no hay coincidencias de búsqueda en lugar de una tarjeta descriptiva con acción de reset.
3. **Escalabilidad de Selectores de Documentos:**
   - *Diagnóstico:* Formularios de series y plantillas utilizan elementos `<select>` nativos con más de 30 opciones sin funcionalidad de búsqueda rápida o autocompletado (`SearchSelect`).

### 🟡 Hallazgos de Mejora (P2)
1. **Espaciado y Densidad en Formularios Modales:**
   - *Diagnóstico:* Modales como `CreateBranchModal`, `CreateRoleModal` y `CreateUserModal` presentan campos en una sola columna vertical con padding excesivo (24px+), desperdiciando espacio horizontal.
2. **Disparidad en Badges de Estado:**
   - *Diagnóstico:* Se encontraron más de 4 convenciones de colores y bordes para estados similares (`ACTIVE`, `EMITTED`, `ISSUED`, `APPROVED`).
3. **Falta de Sticky Headers en Tablas Operativas:**
   - *Diagnóstico:* En tablas con scroll vertical (ej. Auditoría, Catálogo con 35 ítems), los encabezados de columna se pierden al desplazarse hacia abajo.

### 🟢 Hallazgos Cosméticos (P3)
1. **Inconsistencias en Jerarquía Tipográfica:**
   - *Diagnóstico:* Variación en tamaños de títulos (de 18px a 24px) y presencia inconsistente de subtítulos tipo eyebrow (`.dm-eyebrow`).
2. **Múltiples Radios de Borde:**
   - *Diagnóstico:* Coexistencia de `borderRadius: 4px`, `6px`, `8px`, `12px` y `9999px` sin un token central.

---

## 3. Matriz Completa de Pantallas (SCREEN_AUDIT_MATRIX)

| Módulo | Ruta | Título de Página | Acción Primaria | Acciones Secundarias | Modales Asociados | Tablas | Formularios | Filtros | Empty State | Loading State | Error State | Responsive (1024-1920) | Prioridad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Auth** | `/login` | Iniciar Sesión | Ingresar al sistema | Acceso demo rápido | Ninguno | 0 | 1 | 0 | N/A | Spinner botón | Alert rojo | 100% OK | P2 |
| **Doc: Catálogo** | `/documents` | Catálogo documental | Refrescar catálogo | Filtrar por familia | `DocumentVersionDetailModal` | 1 | 0 | Familia, Alcance, Búsqueda | Básico | Spinner central | Toast/Alert | Requiere scroll | P1 |
| **Doc: Numeración** | `/documents/numbering` | Estándar de numeración | Configurar regla | Probar formateo | `FormatTestModal` | 1 | 1 | Familia | Básico | Spinner central | Toast | OK | P2 |
| **Doc: Series** | `/documents/series` | Series digitales y talonarios | Crear Serie | Reservar Rango, Anular | `CreateSeriesModal`, `ReserveRangeModal`, `VoidNumberModal` | 2 | 2 | Tipo, Sede, Periodo | Básico | Spinner central | StepUpDialog / Toast | OK | P1 |
| **Doc: Plantillas** | `/documents/templates` | Plantillas Documentales y Renderizado | Ver Muestra PDF | Descargar PDF, Cambiar Estado/Escenario | `PdfTemplatePreviewModal` | 2 | 1 | Tabs por familia (5) | Básico | Spinner WeasyPrint | Modal error | Requiere optimizar | P0 |
| **Organización** | `/organization` | Estructura y almacenes | Nueva Sede | Nuevo Almacén, Nueva Zona, Eliminar | `CreateBranchModal`, `CreateWarehouseModal`, `CreateZoneModal` | 1 (Árbol) | 3 | Árbol jerárquico | Básico | Spinner lateral | StepUpDialog / Alert | Desborde lateral en 1024 | P1 |
| **Seguridad: Roles** | `/admin/roles` | Control de Acceso RBAC | Nuevo Rol | Editar permisos, Matriz SoD | `CreateRoleModal`, `EditPermissionsModal` | 3 | 1 | Pestañas de matriz (5) | Básico | Spinner central | Toast | OK | P1 |
| **Seguridad: Permisos** | `/admin/permissions` | Catálogo de Permisos | Sincronizar catálogo | Ver roles asignados | `PermissionDetailModal` | 1 | 0 | Búsqueda, Módulo | Básico | Spinner central | Toast | OK | P2 |
| **Seguridad: Usuarios** | `/admin/users` | Administración de usuarios | Nuevo Usuario | Asignar roles, Suspender | `CreateUserModal`, `AssignRolesModal` | 1 | 1 | Búsqueda por email | Básico | Spinner central | Toast | OK | P2 |
| **Auditoría** | `/audit` | Registro unificado de auditoría | Exportar CSV | Aplicar filtros, Limpiar | `AuditDetailModal` | 1 | 1 | Recurso, Acción, Resultado, Actor, UUID | Básico | Spinner central | Toast | Tablas anchas con scroll | P1 |
| **Seguridad: MFA** | `/security` | Seguridad y doble factor | Configurar TOTP | Regenerar llaves | `StepUpDialog`, `TotpSetupModal` | 0 | 1 | Ninguno | N/A | Spinner botón | Alert rojo | OK | P1 |
| **Sistema** | `/system` | Estado de infraestructura | Actualizar estado | Ver variables | Ninguno | 1 | 0 | Ninguno | N/A | Spinner central | Badge error | OK | P3 |

---

## 4. Inventario Completo de Modales (MODAL_INVENTORY)

| N° | Módulo | Nombre Técnico | Propósito Operativo | Tipo | Ancho Actual | Alto Actual | Comportamiento Scroll | Botón Primario | Botón Secundario | Acción Cierre | Responsive | Patrón Recomendado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Organización | `CreateBranchModal` | Registro de nueva sede física y geolocalización | CREATE | `600px` (inline) | Auto | Body scroll | Guardar Sede | Cancelar | Backdrop / Esc | Borde ajustado | `MODAL_LG` (2 columnas) |
| 2 | Organización | `CreateWarehouseModal` | Creación de almacén dentro de una sede | CREATE | `480px` (inline) | Auto | Body scroll | Guardar Almacén | Cancelar | Backdrop / Esc | OK | `MODAL_MD` |
| 3 | Organización | `CreateZoneModal` | Creación de zona operativa dentro de almacén | CREATE | `480px` (inline) | Auto | Body scroll | Guardar Zona | Cancelar | Backdrop / Esc | OK | `MODAL_MD` |
| 4 | Seguridad | `CreateRoleModal` | Alta de nuevo perfil de rol RBAC personalizado | CREATE | `540px` (inline) | Auto | Body scroll | Guardar Rol | Cancelar | Backdrop / Esc | OK | `MODAL_MD` |
| 5 | Seguridad | `CreateUserModal` | Alta de usuario e invitación con roles | CREATE | `540px` (inline) | Auto | Body scroll | Crear Usuario | Cancelar | Backdrop / Esc | OK | `MODAL_MD` |
| 6 | Series | `CreateSeriesModal` | Creación de serie digital anual por sede y tipo | CREATE | `520px` (inline) | Auto | Body scroll | Crear Serie | Cancelar | Backdrop / Esc | OK | `MODAL_MD` |
| 7 | Series | `ReserveRangeModal` | Reserva atómica y concurrente de correlativos | ASSIGN | `520px` (inline) | Auto | Body scroll | Confirmar Reserva | Cancelar | Backdrop / Esc | OK | `MODAL_MD` |
| 8 | Series | `VoidNumberModal` | Anulación formal de correlativo con justificación | DANGER_CONFIRM | `460px` (inline) | Auto | Contenido fijo | Anular Correlativo | Cancelar | Backdrop / Esc | OK | `MODAL_SM` |
| 9 | Catálogo | `DocumentVersionDetailModal` | Inspección de esquema y versiones inmutables | VERSION_DETAIL | `700px` (inline) | `80vh` | Table scroll | Cerrar | Exportar JSON | Botón X | Desborde vertical | `DRAWER_RIGHT` |
| 10 | Plantillas | `PdfTemplatePreviewModal` | Previsualización y descarga de muestras PDF | PDF_PREVIEW | `1050px` (inline) | `92vh` | Frame aislado | Descargar PDF | Cerrar | Botón X | Desborde <1200px | `FULLSCREEN_DIALOG` |
| 11 | Auth / MFA | `StepUpDialog` | Verificación TOTP para acciones de alto riesgo (428) | STEP_UP | `420px` (CSS) | Auto | Fijo | Verificar y Ejecutar | Cancelar | Botón X / Cancelar | OK | `MODAL_SM` |
| 12 | Auditoría | `AuditDetailModal` | Visualización del payload antes/después del evento | DETAIL | `680px` (inline) | `75vh` | Code scroll | Cerrar | Copiar JSON | Botón X | OK | `DRAWER_RIGHT` |

---

## 5. Detección de Mal Uso de Modales y Propuesta de Transformación

1. **`DocumentVersionDetailModal` → `DRAWER_RIGHT`:**
   - *Razón:* Muestra historial cronológico y JSON de esquema. Un cajón lateral deslizante permite comparar la versión mientras se mantiene visible la tabla principal del catálogo.
2. **`PdfTemplatePreviewModal` → `FULLSCREEN_DIALOG`:**
   - *Razón:* La previsualización de documentos A4 requiere el 95% de la pantalla para evitar distorsiones tipográficas y facilitar la auditoría de firmas y QR.
3. **`AuditDetailModal` → `DRAWER_RIGHT`:**
   - *Razón:* Permite inspeccionar diffs JSON sin perder el contexto de la lista de eventos de auditoría.

---

## 6. Auditoría Específica del Visor PDF (F014 — F018)

- **Distribución Actual de Espacio:**
  - Encabezado modal + Subtítulo técnico: `80px`
  - Barra de controles (Estado + Escenario + Selector Líneas): `56px`
  - Visor iframe WeasyPrint: `Restante (~70%)`
- **Problema Detectado:** En pantallas estándar (1366x768), el documento PDF queda confinado a menos de 500px de altura, obligando al usuario a realizar scroll vertical continuo.
- **Propuesta Arquitectónica:**
  - Barra superior ultracompacta (`44px`) con título, badge de estado, selector de escenario inline y botones de acción (Descargar PDF / Modo HTML / Cerrar).
  - Maximización del viewport documental al `94%` de la altura útil.

---

## 7. Sistema Unificado de Tamaños de Modal (MODAL_SYSTEM)

```
┌─────────────────────────────────────────────────────────────┐
│ MODAL SYSTEM SPECIFICATION                                   │
├───────────┬───────────┬─────────────────────────────────────┤
│ Tamaño    │ Ancho Máx │ Propósito Operativo                 │
├───────────┼───────────┼─────────────────────────────────────┤
│ SM        │ 400px     │ Confirmaciones, Peligro, Step-Up MFA│
│ MD        │ 540px     │ Formularios simples (1-6 campos)    │
│ LG        │ 720px     │ Formularios complejos / 2 columnas  │
│ XL        │ 960px     │ Tablas de asignación y matrices     │
│ FULL      │ 96vw×94vh │ Visor PDF y flujos de pantalla comp.│
│ DRAWER    │ 480-600px │ Detalle, historial JSON y versiones │
└───────────┴───────────┴─────────────────────────────────────┘
```

---

## 8. Sistema Tipográfico y Jerarquía Visual

- **Fuente Base:** Inter, system-ui, -apple-system, sans-serif.
- **Escala Canónica:**
  - `Display / Page Title:` `20px` (font-weight: 700, line-height: 1.25, color: `#0f172a`)
  - `Section / Card Title:` `15px` (font-weight: 600, color: `#1e293b`)
  - `Table Header / Eyebrow:` `11px` (font-weight: 700, text-transform: uppercase, letter-spacing: 0.05em, color: `#64748b`)
  - `Body / Cell Text:` `13px` (font-weight: 400, color: `#334155`)
  - `Caption / Helper Text:` `11px` (font-weight: 400, color: `#64748b`)
  - `Monospace (SKU, IDs, Hashes):` `12px` (`ui-monospace`, `SFMono-Regular`, monospace)

---

## 9. Densidad Visual y Política de Cards

- **Principio Operativo:** La plataforma logística requiere **alta densidad útil** sin saturación cognitiva.
- **Reglas de Contención:**
  - Reemplazar "cards dentro de cards" por separadores lineales sutiles (`border: 1px solid #e2e8f0`).
  - Reducir padding de contenedores principales de `24px` a `16px`.
  - Altura de filas de tabla (`table tr`): `38px` a `42px` (anteriormente hasta 56px).
  - Altura de controles de entrada (`input`, `select`, `button`): `34px` estándar.

---

## 10. Arquitectura de Navegación Propuesta

Actualmente, el menú lateral contiene 11 enlaces directos sin jerarquía. Para garantizar escalabilidad hasta la Fase 100, se propone la siguiente estructura semántica colapsable:

```
NEXUS LOGISTICS (Sidebar Reestructurado)
│
├── 📦 GOBIERNO DOCUMENTAL
│   ├── Catálogo Canónico (/documents)
│   ├── Reglas de Numeración (/documents/numbering)
│   ├── Series y Talonarios (/documents/series)
│   └── Plantillas y Render (/documents/templates)
│       ├── Compras (F015)
│       ├── Recepción (F016)
│       ├── Inventario (F017)
│       └── Salida y Despacho (F018)
│
├── 🏭 RED LOGÍSTICA & ALMACENES
│   └── Estructura Organizacional (/organization)
│       ├── Sedes Físicas
│       ├── Almacenes
│       └── Zonas WMS
│
├── 🛡️ ADMINISTRACIÓN & SEGURIDAD
│   ├── Roles y Permisos RBAC (/admin/roles)
│   ├── Directorio de Usuarios (/admin/users)
│   ├── Doble Factor MFA (/security)
│   └── Trazabilidad & Auditoría (/audit)
│
└── ⚙️ SISTEMA
    └── Estado de Infraestructura (/system)
```

---

## 11. Estados de Badges y Feedback Unificado

| Estado | Fondo (`bg`) | Texto (`color`) | Borde (`border`) | Significado Operativo |
|---|---|---|---|---|
| `ACTIVE` / `ISSUED` | `#ecfdf5` | `#065f46` | `#a7f3d0` | Operativo, vigente o emitido conforme |
| `PENDING` / `SCHEDULED` | `#fffbeb` | `#92400e` | `#fde68a` | En espera de acción o programación |
| `IN_PROGRESS` / `PICKING` | `#eff6ff` | `#1d4ed8` | `#bfdbfe` | Tarea activa en almacén |
| `APPROVED` | `#f0fdf4` | `#15803d` | `#bbf7d0` | Autorizado formalmente |
| `VOID` / `CANCELLED` | `#fef2f2` | `#991b1b` | `#fecaca` | Anulado formalmente sin reutilización |
| `ERROR` / `REJECTED` | `#fff1f2` | `#be123c` | `#fecdd3` | Falla o rechazo técnico |
| `DRAFT` | `#f8fafc` | `#475569` | `#e2e8f0` | Borrador editable con marca de agua |

---

## 12. Componentes Compartidos a Crear en Fase de Rediseño

1. `PageHeader`: Título, eyebrow, descripción y barra de acciones principales.
2. `ModalShell`: Contenedor base accesible (ARIA dialog, focus lock, escape key, overlay, header, footer).
3. `DetailDrawer`: Panel deslizante lateral para inspección profunda.
4. `DataTable`: Tabla con virtualización ligera, sticky header, ordenamiento, selección y paginación.
5. `FilterBar`: Barra modular con búsqueda debounce, selects temáticos y botón de reinicio.
6. `SearchSelect`: Selector desplegable con búsqueda filtrada en tiempo real.
7. `StatusBadge`: Etiqueta semántica unificada.
8. `EmptyState`: Ilustración sutil, mensaje de contexto y botón de acción reparadora.
9. `LoadingOverlay`: Indicador de carga semántico no bloqueante.
10. `ConfirmDialog`: Modal de confirmación estándar y destructivo.
11. `PDFViewerModal`: Visor a pantalla completa con zoom, descarga y modo interactivo HTML.

---

## 13. Gaps de Backend y Fases Propietarias Futuras (F051 — F060)

| Funcionalidad Observada | Clasificación | Fase Propietaria Canónica | Acción en Esta Auditoría |
|---|---|---|---|
| Creación de pedidos reales de clientes | `FUTURE_PHASE_OWNER` | **F051 (Pedidos de Salida)** | NO implementar en F018 |
| Algoritmo de reserva de stock FIFO | `FUTURE_PHASE_OWNER` | **F052 (Reserva de Stock)** | NO implementar en F018 |
| Olas de picking y escaneo de códigos de barra | `FUTURE_PHASE_OWNER` | **F053 (Picking Operativo)** | NO implementar en F018 |
| Pesaje en balanza y generación SSCC | `FUTURE_PHASE_OWNER` | **F054 (Packing Operativo)** | NO implementar en F018 |
| Planificación de viajes y muelles de salida | `FUTURE_PHASE_OWNER` | **F055 (Planificación Despacho)** | NO implementar en F018 |
| Colocación y traba física de precintos | `FUTURE_PHASE_OWNER` | **F058 (Carga y Precintos)** | NO implementar en F018 |

---

## 14. Plan de Ejecución del Rediseño (Priorizado)

```
FASE DE REDISEÑO POST-AUDITORÍA (Orden de Implementación Sugerido):
1. [P0] Creación de Design Tokens y Sistema Base de Modales (ModalShell, ConfirmDialog, Drawer).
2. [P0] Reestructuración del Visor PDF (Fullscreen Dialog con maximización del área del documento).
3. [P0] Reorganización de Navegación Lateral y Soporte Responsive / Drawer Móvil.
4. [P1] Refactorización de Formularios (Layout de 2 columnas en modales LG/MD).
5. [P1] Estandarización de Tablas (Sticky headers, padding 8px, Empty states unificados).
6. [P2] Unificación de Badges, Botones y Jerarquía Tipográfica.
```

---

## 15. Identificadores de Estado de la Auditoría

```
PHASE: POST_F018_VISUAL_AUDIT
F018_STATUS: APPROVED
F019_STARTED: 0
WALKTHROUGH_PHASE_MAPPING: CANONICAL
REDESIGN_IMPLEMENTED: 0
TOTAL_ROUTES_AUDITED: 11
TOTAL_PAGES_AUDITED: 11
TOTAL_MODALS_FOUND: 12
TOTAL_TABLES_AUDITED: 14
TOTAL_FORMS_AUDITED: 9
P0_FINDINGS: 2
P1_FINDINGS: 3
P2_FINDINGS: 3
P3_FINDINGS: 2
UI_ONLY_GAPS: 4
BACKEND_CONTRACT_GAPS: 0
FUTURE_PHASE_OWNER_FINDINGS: 6
ALL_EXISTING_ROUTES_AUDITED: PASS
ALL_EXISTING_MODALS_INVENTORIED: PASS
RESPONSIVE_AUDIT: PASS
ZOOM_100_AUDIT: PASS
NAVIGATION_AUDIT: PASS
TABLE_AUDIT: PASS
FORM_AUDIT: PASS
PDF_PREVIEW_AUDIT: PASS
MFA_MODAL_AUDIT: PASS
DESIGN_SYSTEM_PROPOSAL: PASS
MODAL_SYSTEM_PROPOSAL: PASS
REPORT: docs/ui/visual-audit-f001-f018.md
FINAL_STATUS: VISUAL_AUDIT_READY_FOR_REVIEW
```
