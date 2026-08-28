# Sistema Logístico Integral — Definición Formal del Alcance

Este documento define de manera exhaustiva y canónica el alcance funcional, técnico y operativo del **Sistema Logístico Integral**.

---

## 1. Módulo 1 — Compras y Adquisiciones
- **Requerimientos de Compra (PR):** Solicitudes internas generadas por necesidad operativa o reposición de stock mínimo/punto de reorden.
- **Solicitudes de Cotización (RFQ):** Emisión y distribución formal a múltiples proveedores homologados.
- **Cotizaciones de Proveedores:** Registro estructurado de ofertas con precios unitarios, descuentos, plazos de entrega, costos de flete e impuestos.
- **Evaluación y Comparación:** Cuadro comparativo automatizado en backend con scoring por costo, tiempo y cumplimiento histórico.
- **Órdenes de Compra (PO):** Generación formal de órdenes de compra con versionado, términos comerciales y condiciones de entrega.
- **Flujos de Aprobación:** Workflows multinivel basados en montos, centros de costo y jerarquía organizativa.
- **Seguimiento de OC:** Trazabilidad de estados (`DRAFT`, `PENDING_APPROVAL`, `APPROVED`, `SENT`, `PARTIALLY_RECEIVED`, `COMPLETED`, `CANCELLED`).
- **Entregas Parciales y Liquidación:** Vinculación estricta entre líneas de OC y recepciones de almacén.

---

## 2. Módulo 2 — Recepción e Inbound
- **Aviso de Llegada / ASN (Advanced Shipping Notice):** Notificación previa del proveedor con detalle de bultos, transportista y fecha estimada.
- **Gestión de Citas (Slot Booking):** Planificación de ventanas horarias por muelle y sede para evitar cuellos de botella.
- **Control de Puerta / Garita:** Registro de ingreso vehicular, placa, conductor, empresa de transporte, hora de entrada y precintos.
- **Asignación de Muelles (Dock Management):** Asignación dinámica de puertas de descarga según tipo de vehículo y carga.
- **Descarga e Inspección:** Descarga física, conteo ciego o guiado, validación de condiciones de transporte (temperatura, embalaje).
- **Escaneo y Verificación:** Escaneo por código de barras / QR de bultos, artículos, lotes y series.
- **Control de Discrepancias:** Detección y registro formal de faltantes, sobrantes, mermas y productos dañados.
- **Recepción Parcial / Total:** Liquidación de recepción con generación automática de Acta de Recepción y pase al Kardex.

---

## 3. Módulo 3 — Almacenes y Topología Espacial
- **Jerarquía Topológica:** Organización $\rightarrow$ Sede $\rightarrow$ Almacén $\rightarrow$ Zona (Recepción, Picking, Reserva, Cuarentena, Despacho) $\rightarrow$ Pasillo $\rightarrow$ Rack $\rightarrow$ Nivel $\rightarrow$ Posición.
- **Capacidades y Restricciones:** Control de peso máximo, volumen, dimensiones, compatibilidad química y temperatura controlada por ubicación.
- **Identificación Estándar:** Códigos de ubicación estructurados y etiquetas con códigos QR para lectura rápida en terminales.
- **Mapa Lógico:** Representación topológica de ubicaciones con estado de ocupación, bloqueo y disponibilidad en tiempo real.

---

## 4. Módulo 4 — Inventario y Kardex Inmutable
- **Regla Fundamental de Inventario:** **NUNCA** se modifica un saldo directamente. Todo cambio cuantitativo o cualitativo debe originarse a partir de un movimiento de inventario inmutable.
- **Kardex Inmutable:** Registro secuencial e inalterable de cada transacción con timestamp, usuario, tipo de movimiento, documento origen, ubicación origen/destino y cantidad.
- **Estados de Stock:**
  - *Físico Total:* Cantidad real en instalaciones.
  - *Disponible:* Libre para asignación y picking.
  - *Reservado:* Comprometido con órdenes de salida activas.
  - *Bloqueado / Cuarentena:* En inspección técnica o retención por calidad.
  - *En Tránsito:* En transferencia entre almacenes o sedes.
  - *Dañado / Vencido:* Segregado para reclamo o descarte.
- **Trazabilidad por Lotes y Series:** Control estricto de fecha de fabricación, fecha de vencimiento y números de serie unitarios.
- **Operaciones de Almacén:**
  - *Putaway (Ubicación):* Reglas dirigidas de almacenamiento según rotación (ABC), volumen y afinidad.
  - *Transferencias:* Traslado entre ubicaciones, zonas o almacenes inter-sede.
  - *Conteos Físicos:* Inventarios cíclicos y generales con conteo ciego y generación de ajustes auditados.

---

## 5. Módulo 5 — Trazabilidad Integral (End-to-End Lineage)
- **Cadena de Custodia Completa:** Reconstrucción cronológica y gráfica del flujo de vida de un ítem:
  $$\text{OC} \longrightarrow \text{Recepción} \longrightarrow \text{Kardex} \longrightarrow \text{Ubicación} \longrightarrow \text{Picking} \longrightarrow \text{Packing} \longrightarrow \text{Despacho} \longrightarrow \text{Viaje/Ruta} \longrightarrow \text{Entrega (POD)}$$
- **Eventos Auditables:** Cada transición registra operador, hora precisa, geolocalización (cuando aplique), documento de sustento y snapshot del estado anterior.

---

## 6. Módulo 6 — Salida y Despacho (Outbound)
- **Pedidos de Salida (Sales / Transfer Orders):** Requerimientos de despacho con validación de crédito/aprobación previa.
- **Reserva y Asignación de Stock:** Reserva lógica automática según estrategias FIFO (First-In, First-Out) o FEFO (First-Expired, First-Out).
- **Ola de Picking:** Agrupación eficiente de pedidos por zona, ruta o cliente (Wave / Batch / Cluster picking).
- **Packing y Verificación:** Control de empaque, pesaje, cubicaje y etiquetado de bultos con identificador único (SSCC / QR).
- **Liberación y Estaging:** Consolidación en zona de pre-despacho y validación final de bultos.
- **Carga y Precintado:** Registro de orden de carga vehicular, distribución de peso y numeración de precintos de seguridad.
- **Emisión de Manifiestos:** Generación del Manifiesto de Carga y Guía de Remisión de Transporte.

---

## 7. Módulo 7 — Transporte y Gestión de Flota
- **Catálogo de Unidades:** Registro de vehículos propios y tercerizados con placa, tipo, capacidad de carga (kg/m³), SOAT, revisiones técnicas y permisos.
- **Conductores y Transportistas:** Ficha de conductor, licencia de conducir con categoría y vigencia, asignación de unidad.
- **Planificación de Viajes:** Asignación de vehículo, conductor, manifiesto de despacho y paradas programadas.
- **Control de Viaje e Incidencias:** Monitoreo del recorrido, registro de demoras mecánicas, clima o contingencias en ruta.

---

## 8. Módulo 8 — Motor de Rutas y Navegación
- **Geocodificación Real:** Normalización y conversión de direcciones a coordenadas latitud/longitud precisas en backend.
- **Motor de Ruteo Real:** Integración vía backend con proveedores autorizados (OSRM / OpenRouteService) para cálculo de distancias reales por red vial, duración estimada y polilíneas vectoriales.
- **Visualización en Frontend:** Renderizado mediante **MapLibre GL** consumiendo exclusivamente geometrías y waypoints procesados por el backend.
- **Geocercas y Checkpoints:** Detección de arribo y salida de puntos de entrega mediante validación perimetral.
- **Prohibición Estricta:** Quedan terminantemente prohibidas polilíneas falsas o simulaciones sintéticas en entornos productivos.

---

## 9. Módulo 9 — Entrega y Prueba de Entrega (POD)
- **Recepción en Destino:** Validación de identidad del receptor (DNI/documento, nombre, cargo).
- **Evidencias de Entrega:**
  - Coordenadas GPS del punto exacto de entrega.
  - Firma digital en pantalla capturada y transferida al backend.
  - Fotografías de la mercancía entregada y fachada/guía firmada.
  - Código OTP (One-Time Password) de confirmación cuando sea requerido.
- **Resultados de Entrega:** Entrega Conforme Total, Entrega Parcial (con detalle de ítems rechazados) o Rechazo Total con motivo tipificado.

---

## 10. Módulo 10 — Logística Inversa
- **Autorización de Devolución (RMA):** Registro de solicitud de devolución asociada a la entrega original y motivo fundado.
- **Orden de Recojo:** Planificación de parada de transporte para recuperación del producto.
- **Inspección Técnica de Ingreso:** Evaluación de estado físico, empaque, funcionalidad y motivo de devolución.
- **Destino del Ítem Devuelto:**
  - *Reingreso a Stock Disponible:* Si el producto está apto.
  - *Cuarentena / Reparación:* Para reacondicionamiento.
  - *Devolución a Proveedor:* En caso de defecto de origen cubierto por garantía.
  - *Baja / Scrap:* Descarte documentado de mercancía no recuperable.

---

## 11. Módulo 11 — Motor Documental y Formatos
- **Autoridad Centralizada:** **Todos** los documentos oficiales se generan exclusivamente en el backend.
- **Catálogo Documental:** Órdenes de Compra, Actas de Recepción, Guías de Remisión, Manifiestos de Despacho, Hojas de Ruta, Actas de Entrega / POD y Certificados de Devolución.
- **Estructura Documental:**
  - Series y correlativos automáticos controlados por backend.
  - Snapshot inmutable de los datos al momento de emisión (protegido contra modificaciones retroactivas).
  - Código QR con datos de validación y URL de verificación.
  - Hash criptográfico (SHA-256) para garantizar integridad.
- **Formatos de Salida:** PDF vectorial optimizado, Excel estructurado (XLSX), CSV delimitado y archivos comprimidos ZIP para descargas masivas.

---

## 12. Módulo 12 — Indicadores Clave de Desempeño (KPIs)
- **Cálculo 100% Backend:** Los indicadores se consolidan mediante consultas y algoritmos analíticos en backend; la UI solo renderiza gráficos y tablas.
- **Métricas Oficiales:**
  - *Compras:* Lead time de proveedores, cumplimiento OTIF de proveedores, variación de precios de compra.
  - *Recepción:* Tiempo promedio de espera en garita, tiempo de descarga, Dock-to-Stock time, porcentaje de discrepancias en recepción.
  - *Inventario:* Exactitud de registro de inventario (IRA), rotación de stock, días de cobertura, índice de mermas/vencimientos.
  - *Despacho:* Order Fill Rate, On-Time In-Full (OTIF) de despacho, productividad de picking/packing (líneas/hora).
  - *Transporte y Entrega:* Cumplimiento de ventana horaria (On-Time Delivery), costo por kilómetro, ratio de entregas fallidas vs exitosas.

---

## 13. Módulo 13 — Integraciones Externas
- **Flujo Obligatorio:** Frontend $\rightarrow$ FastAPI Backend $\rightarrow$ Servicio Externo Autorizado $\rightarrow$ FastAPI Backend $\rightarrow$ Frontend.
- **Servicios Previstos:** Consulta RUC/DNI (SUNAT/RENIEC vía proveedores oficiales), validación técnica de placas/vehículos, motores de geocodificación y ruteo vial, y almacenamiento de archivos/evidencias (Supabase Storage / Cloud Storage).

---

## 14. Módulo 14 — Seguridad Transversal y Control de Acceso (RBAC)
- **Modelo de Autorización:** Role-Based Access Control (RBAC) con scoping multi-tenant por Organización, Sede y Almacén.
- **Auditoría Transversal:** Trazabilidad de operaciones críticas (quién, cuándo, desde qué IP, recurso afectado, payload sanitizado).

---

## 15. Mapa Canónico de Fases (F001 — F100)
- **F001 — F010:** Fundamentos, Baseline, Arquitectura, Modelo de Datos Base y Seguridad Transversal.
- **F011 — F020:** Motor Documental, Plantillas, Correlativos y Generación de Archivos.
- **F021 — F030:** Maestros Logísticos (Organizaciones, Sedes, Almacenes, Catálogo de Productos, Proveedores, Clientes).
- **F031 — F040:** Compras, RFQs, Órdenes de Compra, Citas y Recepción en Muelle.
- **F041 — F050:** Inventario, Kardex Inmutable, Lotes, Series, Ubicaciones y Conteos Cíclicos.
- **F051 — F060:** Salida, Picking, Packing, Control de Embalaje y Despacho.
- **F061 — F070:** Transporte, Flota, Conductores, Ruteo Vial y Mapas.
- **F071 — F080:** Ejecución de Entregas, POD Móvil, Evidencias y Logística Inversa.
- **F081 — F090:** Dashboards, Analítica Avanzada, KPIs Logísticos y Exportaciones Masivas.
- **F091 — F100:** Hardening de Seguridad, Auditoría Integral, Optimización de Rendimiento y Despliegue en Producción (Cloud Run).
