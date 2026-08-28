# Límites de Módulos (Module Boundaries)

Este documento establece formalmente las fronteras de responsabilidad, pertenencia de datos, contratos de entrada/salida y asignación de fases para cada dominio del **Sistema Logístico Integral**.

---

### Módulo: Maestros y Organización (Master Data & Multi-tenancy)
- **RESPONSIBILITY:** Gestionar la estructura jerárquica de la empresa (Organizaciones, Sedes, Almacenes), socios comerciales (Proveedores, Clientes) y catálogo de productos (SKUs, categorías, unidades de medida).
- **INPUT:** Datos de registro de empresas, sucursales, almacenes, catálogos maestros y datos de consulta RUC/DNI.
- **OUTPUT:** Entidades maestras normalizadas, activas y validadas para consumo por los módulos operativos.
- **OWNS_DATA:** `organizations`, `branches`, `warehouses`, `business_partners`, `products`, `product_categories`, `units_of_measure`.
- **DOES_NOT_OWN:** Saldos de inventario, órdenes de compra, hojas de ruta o transacciones de despacho.
- **FUTURE_PHASES:** F021 — F030.

---

### Módulo: Compras y Adquisiciones (Procurement)
- **RESPONSIBILITY:** Orquestar el flujo de abastecimiento desde el requerimiento interno hasta la emisión y seguimiento de órdenes de compra a proveedores.
- **INPUT:** Requerimientos de compra, cotizaciones de proveedores, reglas de aprobación.
- **OUTPUT:** Órdenes de compra aprobadas, snapshots de términos comerciales, alertas de entrega esperada para recepción.
- **OWNS_DATA:** `purchase_requisitions`, `rfqs`, `supplier_quotations`, `purchase_orders`, `purchase_order_lines`, `po_approvals`.
- **DOES_NOT_OWN:** Movimientos físicos de ingreso, saldos de stock en almacén, pagos contables a proveedores.
- **FUTURE_PHASES:** F031 — F035.

---

### Módulo: Recepción e Ingreso (Inbound & Receiving)
- **RESPONSIBILITY:** Administrar la llegada física de mercancías, control de garita/muelles, inspección cuantitativa/cualitativa y liquidación del ingreso.
- **INPUT:** Citas de llegada, órdenes de compra aprobadas, documentos de despacho del proveedor, escaneo de bultos/series.
- **OUTPUT:** Actas de recepción conforme/discrepante, eventos de movimiento de inventario para el Kardex, alertas de diferencias.
- **OWNS_DATA:** `inbound_appointments`, `gate_entries`, `receiving_sessions`, `receiving_items`, `receiving_discrepancies`.
- **DOES_NOT_OWN:** Definición de órdenes de compra, saldos finales de kardex, rutas de transporte de proveedores.
- **FUTURE_PHASES:** F036 — F040.

---

### Módulo: Topología de Almacén (Warehouse Spatial Layout)
- **RESPONSIBILITY:** Modelar la distribución física y lógica de las instalaciones (zonas, pasillos, racks, niveles, posiciones) y sus restricciones técnicas.
- **INPUT:** Planos de almacén, definición de capacidades, dimensiones, tipos de almacenamiento y restricciones de temperatura/peligrosidad.
- **OUTPUT:** Matriz de ubicaciones con estado de ocupación, códigos QR de ubicación y reglas de proximidad.
- **OWNS_DATA:** `warehouse_zones`, `warehouse_locations`, `location_capacities`, `location_constraints`.
- **DOES_NOT_OWN:** Kardex de transacciones de inventario, asignación de pedidos de venta.
- **FUTURE_PHASES:** F041 — F043.

---

### Módulo: Inventario y Kardex (Inventory Core)
- **RESPONSIBILITY:** Garantizar la integridad absoluta del inventario mediante un ledger inmutable de movimientos (Kardex), administrando saldos por estado, lote y serie.
- **INPUT:** Eventos de recepción, órdenes de reserva, transferencias internas, putaway, ajustes de conteo físico.
- **OUTPUT:** Movimientos inmutables registrados, proyección de stock disponible/reservado/bloqueado, valorización y auditoría de saldos.
- **OWNS_DATA:** `inventory_movements`, `stock_balances_view`, `inventory_lots`, `inventory_serials`, `cycle_counts`, `stock_adjustments`.
- **DOES_NOT_OWN:** Aprobaciones de órdenes de compra, despacho vehicular, cobranza o facturación.
- **FUTURE_PHASES:** F044 — F050.

---

### Módulo: Salida, Picking y Packing (Outbound & Dispatch)
- **RESPONSIBILITY:** Gestionar la preparación de pedidos de clientes/transferencias, la reserva de stock (FIFO/FEFO), la generación de olas de picking, el control de empaque (packing) y la consolidación de carga.
- **INPUT:** Pedidos de salida aprobados, disponibilidades de stock, criterios de agrupación por zona/ruta.
- **OUTPUT:** Listas de picking, bultos empacados y etiquetados (SSCC/QR), manifiestos de despacho, eventos de deducción de Kardex.
- **OWNS_DATA:** `outbound_orders`, `outbound_reservations`, `picking_waves`, `picking_tasks`, `packing_boxes`, `packing_items`, `dispatch_manifests`.
- **DOES_NOT_OWN:** Negociación comercial de precios, ejecución de la conducción vehicular en carretera.
- **FUTURE_PHASES:** F051 — F060.

---

### Módulo: Transporte y Flota (Fleet & Transportation)
- **RESPONSIBILITY:** Administrar las unidades vehiculares, conductores propios/tercerizados, capacidades, vigencias documentales y asignación a viajes.
- **INPUT:** Datos de vehículos, licencias de conducir, SOAT/revisiones técnicas, manifiestos de despacho a transportar.
- **OUTPUT:** Hojas de ruta vehicular, asignación de capacidad de carga (peso/volumen), registro de incidentes vehiculares.
- **OWNS_DATA:** `fleet_vehicles`, `fleet_drivers`, `carrier_companies`, `transport_trips`, `trip_manifest_assignments`, `fleet_incidents`.
- **DOES_NOT_OWN:** Contabilidad de depreciación de activos fijos, preparación de pedidos dentro del almacén.
- **FUTURE_PHASES:** F061 — F064.

---

### Módulo: Rutas, Geocodificación y Navegación (Routing Engine)
- **RESPONSIBILITY:** Geocodificar direcciones de clientes/sedes, calcular distancias y tiempos reales mediante motores de ruteo autorizados y proveer geometrías viales para visualización en MapLibre.
- **INPUT:** Coordenadas de origen, paradas y destinos, ventanas horarias de entrega, restricciones de tránsito pesado.
- **OUTPUT:** Secuencias de ruta optimizadas, polilíneas de ruta reales, tiempos estimados de arribo (ETA), perímetros de geocerca.
- **OWNS_DATA:** `geocoded_locations`, `routing_matrix_cache`, `trip_route_geometries`, `geofence_definitions`.
- **DOES_NOT_OWN:** Estado físico del inventario dentro del vehículo, decisiones contractuales de precios de flete.
- **FUTURE_PHASES:** F065 — F070.

---

### Módulo: Entrega y Prueba de Entrega (Delivery & POD)
- **RESPONSIBILITY:** Gestionar la llegada al destino, validación perimetral (geocerca), captura de evidencias de entrega (GPS, firma digital, fotografías, OTP) y liquidación de paradas.
- **INPUT:** Eventos de arribo a parada, datos del receptor, evidencias fotográficas, firmas digitales, confirmación OTP.
- **OUTPUT:** Actas de Entrega / Proof of Delivery (POD) digitales inmutables, eventos de entrega parcial o rechazo motivado.
- **OWNS_DATA:** `delivery_stops`, `proof_of_deliveries`, `delivery_signatures`, `delivery_photos`, `delivery_rejections`.
- **DOES_NOT_OWN:** Emisión de notas de crédito contables, despacho inicial en almacén de origen.
- **FUTURE_PHASES:** F071 — F075.

---

### Módulo: Logística Inversa (Reverse Logistics & RMAs)
- **RESPONSIBILITY:** Canalizar y procesar mercancías devueltas, inspeccionar técnicamente su estado y determinar el destino de reacondicionamiento, reingreso o baja.
- **INPUT:** Solicitudes de devolución (RMA) asociadas a entregas, motivos de rechazo, inspección técnica en muelle de ingreso.
- **OUTPUT:** Autorizaciones de recojo, actas de inspección técnica, movimientos de inventario hacia stock disponible, cuarentena o scrap.
- **OWNS_DATA:** `rma_requests`, `reverse_pickups`, `reverse_inspections`, `scrap_disposals`.
- **DOES_NOT_OWN:** Devolución monetaria o emisión tributaria de notas de crédito contables.
- **FUTURE_PHASES:** F076 — F080.

---

### Módulo: Motor Documental (Document Engine)
- **RESPONSIBILITY:** Centralizar la generación autoritativa de todos los documentos oficiales del sistema (PDF, XLSX, CSV, ZIP) con series, correlativos, snapshots inmutables, códigos QR y firmas criptográficas hash (SHA-256).
- **INPUT:** Payloads estructurados y validados provenientes de los módulos operativos.
- **OUTPUT:** Archivos binarios generados en backend, URLs firmadas de descarga, metadatos de auditoría documental.
- **OWNS_DATA:** `document_types`, `document_series`, `document_correlatives`, `document_snapshots`, `document_templates`.
- **DOES_NOT_OWN:** Lógica de negocio específica de compras o despachos (solo procesa e imprime los datos formalizados).
- **FUTURE_PHASES:** F011 — F020.

---

### Módulo: Analítica y KPIs (Analytics & Metrics)
- **RESPONSIBILITY:** Consolidar, procesar y calcular todas las métricas de rendimiento operativo logístico a partir de los datos transaccionales del backend.
- **INPUT:** Registros históricos de transacciones, tiempos de ciclo, precisiones de inventario y cumplimientos de entrega.
- **OUTPUT:** Agregaciones analíticas, datasets para dashboards, reportes ejecutivos.
- **OWNS_DATA:** `analytics_snapshots`, `kpi_definitions`, `kpi_thresholds`.
- **DOES_NOT_OWN:** Modificación de registros operativos fuente.
- **FUTURE_PHASES:** F081 — F090.
