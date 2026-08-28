# Servicios e Infraestructura Compartida (Shared Services)

Este documento especifica los boundaries, contratos y asignación de fases para los servicios transversales ubicados en `app/shared/`.

---

## 1. Shared Audit Boundary (`app/shared/audit`)
- **Propósito:** Registrar de forma inmutable cada operación de negocio relevante con actor, acción, recurso afectado, resultado y metadatos.
- **Contrato Principal:** `AuditServiceProtocol.record_event(actor_id, action, resource, result, metadata)`
- **Fase de Implementación:** `F007`

---

## 2. Shared Documents Boundary (`app/shared/documents`)
- **Propósito:** Centralizar la generación de documentos oficiales (PDF vectorial, XLSX estructurado, CSV, ZIP) con códigos QR y hashes de integridad.
- **Contrato Principal:** `DocumentGeneratorProtocol.generate_pdf()`, `DocumentGeneratorProtocol.generate_excel()`
- **Fase de Implementación:** `F011 — F020`

---

## 3. Shared Files Boundary (`app/shared/files`)
- **Propósito:** Gestionar almacenamiento seguro de evidencias fotográficas, firmas digitales y archivos adjuntos mediante URLs firmadas.
- **Contrato Principal:** `ObjectStorageProtocol.upload_file()`, `ObjectStorageProtocol.get_signed_url()`
- **Fase de Implementación:** `F030`

---

## 4. Shared Routing Boundary (`app/shared/routing`)
- **Propósito:** Proveer servicios de geocodificación de direcciones y cálculo de rutas por red vial real mediante motores autorizados (OSRM / OpenRouteService).
- **Contrato Principal:** `RoutingServiceProtocol.geocode_address()`, `RoutingServiceProtocol.calculate_route()`
- **Fase de Implementación:** `F061 — F070`

---

## 5. Shared Integrations Boundary (`app/shared/integrations`)
- **Propósito:** Estandarizar el patrón adaptador para proveedores externos (RUC, placas, pasarelas de notificación) aislando la lógica de negocio de las APIs de terceros.
- **Patrón:** `DomainService` $\rightarrow$ `IntegrationInterface` $\rightarrow$ `ProviderAdapter`
- **Fases de Implementación:** Según requerimiento específico de cada dominio (`F026`, `F062`, `F074`).
