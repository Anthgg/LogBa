# Series Digitales, Reserva Concurrente de Correlativos y Talonarios (Fase 013)

## 1. Arquitectura de Series Digitales

El Sistema Logístico Integral implementa el motor de series digitales para gestionar el ciclo de vida de la numeración de documentos internos (`document_scope = INTERNAL`).

### Ámbito y Unicidad de la Serie
Cada serie documental se encuentra estrictamente circunscrita a cuatro dimensiones operacionales:

$$\mathbf{UNIQUE(organization\_id, document\_type\_id, branch\_id, period\_year)}$$

- **Organización (`organization_id`)**: Aislamiento multi-tenant.
- **Tipo Documental (`document_type_id`)**: Tipos canónicos internos (ej: `PO`, `REQ`, `GRN`, `TRF`, `DSP`).
- **Sede Operativa (`branch_id`)**: Sede emisora correspondiente a la organización del usuario.
- **Año del Periodo (`period_year`)**: Año calendario de vigencia de la serie ($2000 \le \text{year} \le 2100$).

> [!WARNING]
> **Prohibición de Series para Documentos Externos**: Los documentos con alcance `EXTERNAL` (ej. `PSC` Guía de Remisión Proveedor, `BOL`, `EX_INV`) tienen prohibida la creación de series internas (`EXTERNAL_DOCUMENT_SERIES_FORBIDDEN`). Su serie y número oficial legal son preservados intactos (`EXTERNAL_PRESERVED`).

---

## 2. Concurrencia Transaccional y Asignación de Correlativos

La asignación de correlativos individuales y rangos de reserva opera bajo **transacciones ACID de PostgreSQL** con bloqueo pesimista:

```sql
SELECT id, next_correlative, correlative_width, is_active
FROM document_series
WHERE id = :series_id
FOR UPDATE;
```

### Algoritmo Atómico de Reserva
1. **Bloqueo**: `SELECT ... FOR UPDATE` sobre la fila de la serie.
2. **Cálculo de Rango**:
   $$\text{start} = \text{series.next\_correlative}$$
   $$\text{end} = \text{start} + \text{quantity} - 1$$
3. **Validación de Límites**:
   - $1 \le \text{quantity} \le 500$ (`MAX_RESERVATION_SIZE = 500`).
   - $\text{end} \le 999999$ (`CORRELATIVE_RANGE_EXHAUSTED` si supera el límite de 6 dígitos).
4. **Incremento Monótono**: `series.next_correlative = end + 1`.
5. **Persistencia**: Registro de la reserva en `document_number_reservations` e inserción masiva de los números individuales en `document_series_numbers` con estado `RESERVED`.
6. **Compromiso**: `COMMIT` y liberación del lock.

> [!IMPORTANT]
> **Prohibición de `MAX(correlative) + 1`**: Queda estrictamente prohibido el cálculo de correlativos mediante `MAX() + 1` o `COUNT(*) + 1`. La única autoridad atómica es `document_series.next_correlative` protegido por `SELECT FOR UPDATE`.

---

## 3. Política Absoluta de No Reutilización (`REAL_NO_REUSE_ENFORCEMENT = PASS`)

El motor de numeración garantiza que **ningún número asignado pueda volver a emitirse ni reutilizarse**:
- **Monotonicidad Estricta**: `next_correlative` jamás disminuye ni retrocede.
- **Anulación con Trazabilidad (`status = VOIDED`)**: Al anular un correlativo (`POST /document-series/numbers/{id}/void`), se registra `voided_at`, `voided_by_user_id` y el motivo obligatorio (`void_reason`), manteniendo su `display_code` y posición en la serie.
- **Sin Eliminación Destructiva**: No existen endpoints para eliminar series, reservas o números (`RESERVATION_DELETE_API = 0`, `NUMBER_DELETE_API = 0`).

---

## 4. Talonarios Técnicos Descargables (CSV)

La exportación de talonarios permite obtener el inventario de correlativos asociados a una reserva:
- **Endpoint**: `GET /api/logistics/document-series/reservations/{id}/booklet?format=csv`
- **Generación Exclusiva en Backend**: El archivo CSV es generado, validado y formateado por el backend con cabecera `Content-Disposition: attachment; filename="talonario_reserva_...csv"`.
- **Estructura de Columnas**:
  ```csv
  DOCUMENT_TYPE,BRANCH,YEAR,CORRELATIVE,DISPLAY_CODE,STATUS,RESERVED_AT,VOIDED_AT,VOID_REASON,RESERVATION_ID
  ```
- **Seguridad**: Los talonarios técnicos no contienen secretos, tokens, contraseñas ni claves API (`BOOKLET_SECRET_LEAKS = 0`).
- **Límite de Formatos**: En **F013** se entrega formato CSV. La generación visual y plantillas PDF pertenecen a **F014** y **F020** (`BOOKLET_PDF = FUTURE_PHASE_OWNER_F014_F020`).

---

## 5. Matriz de Seguridad RBAC y Step-Up MFA

| Endpoint | Método | Permiso | Nivel de Riesgo | Desafío Step-Up MFA (F009) |
| :--- | :--- | :--- | :--- | :--- |
| `/api/logistics/document-series` | `GET` | `document_series.read` | LOW | No |
| `/api/logistics/document-series` | `POST` | `document_series.create` | HIGH | **HTTP 428 Precondition Required** |
| `/api/logistics/document-series/{id}` | `GET` | `document_series.read` | LOW | No |
| `/api/logistics/document-series/{id}/reservations` | `POST` | `document_series.reserve` | HIGH | **HTTP 428 Precondition Required** |
| `/api/logistics/document-series/reservations/{id}` | `GET` | `document_series.read` | LOW | No |
| `/api/logistics/document-series/{id}/numbers` | `GET` | `document_series.read` | LOW | No |
| `/api/logistics/document-series/numbers/{id}/void` | `POST` | `document_series.void` | HIGH | **HTTP 428 Precondition Required** |
| `/api/logistics/document-series/reservations/{id}/booklet` | `GET` | `document_series.download` | LOW | No |
