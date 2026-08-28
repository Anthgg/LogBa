# Marco de Integraciones Externas (External Integrations Framework)

Este documento define formalmente los servicios externos previstos, su propósito, arquitectura estricta Backend-Only, manejo de secretos, estrategias de contingencia y fase de implementación.

---

### Integración 1: Consulta de RUC y DNI (Business Partner Identity Verification)
- **NAME:** `RUC_DNI_LOOKUP_SERVICE`
- **PURPOSE:** Consultar automáticamente razón social, estado tributario (Habido/Activo), dirección fiscal y representantes legales a partir del RUC (SUNAT) o nombre completo a partir del DNI (RENIEC).
- **BACKEND_ONLY:** `YES` (El frontend jamás se conecta a los proveedores de RUC).
- **SECRET_REQUIRED:** `YES` (Tokens de API del proveedor homologado almacenados en `.env` / Secret Manager).
- **FALLBACK_REQUIRED:** `YES` (Permitir ingreso manual con registro de bandera de auditoría `MANUAL_ENTRY_VERIFICATION_PENDING` en caso de indisponibilidad del servicio externo).
- **SOURCE_EVIDENCE_REQUIRED:** `YES` (Guardar snapshot con timestamp de la respuesta JSON original de SUNAT).
- **PHASE_OWNER:** `F026`

---

### Integración 2: Verificación Técnica Vehicular (Fleet Plate Lookup)
- **NAME:** `VEHICLE_PLATE_LOOKUP_SERVICE`
- **PURPOSE:** Consultar marca, modelo, carga útil máxima y estado de revisiones técnicas/SOAT a partir de la placa de rodaje.
- **BACKEND_ONLY:** `YES`
- **SECRET_REQUIRED:** `YES`
- **FALLBACK_REQUIRED:** `YES` (Registro manual documentado con adjunto de tarjeta de propiedad).
- **SOURCE_EVIDENCE_REQUIRED:** `YES`
- **PHASE_OWNER:** `F062`

---

### Integración 3: Servicio de Geocodificación (Geocoding & Address Normalization)
- **NAME:** `GEOCODING_SERVICE` (Nominatim / Pelias / Google Geocoding API / Mapbox)
- **PURPOSE:** Traducir direcciones textuales de entrega y almacén a coordenadas geográficas normalizadas (Latitud, Longitud) y viceversa (Geocodificación inversa).
- **BACKEND_ONLY:** `YES` (Las coordenadas se validan y persisten desde el backend).
- **SECRET_REQUIRED:** `YES`
- **FALLBACK_REQUIRED:** `YES` (Selección de punto en mapa visual interactivo asistido por el usuario).
- **SOURCE_EVIDENCE_REQUIRED:** `YES` (Almacenar nivel de precisión / `confidence_score`).
- **PHASE_OWNER:** `F065`

---

### Integración 4: Motor de Ruteo Vial y Matrices de Distancia (Routing Engine)
- **NAME:** `ROUTING_ENGINE_SERVICE` (OSRM / OpenRouteService / GraphHopper)
- **PURPOSE:** Calcular matrices de tiempo y distancia por red vial real, optimizar secuencia de paradas de despacho (VRP) y generar polilíneas de ruta reales.
- **BACKEND_ONLY:** `YES`
- **SECRET_REQUIRED:** `YES`
- **FALLBACK_REQUIRED:** `YES` (Cálculo de distancia geodésica / Haversine con factor de corrección vial en caso de caída del motor de rutas).
- **SOURCE_EVIDENCE_REQUIRED:** `YES` (Geometría GeoJSON/Polyline oficial devuelta por el motor persistida en el backend).
- **PHASE_OWNER:** `F066`

---

### Integración 5: Almacenamiento de Archivos y Evidencias (Object Storage)
- **NAME:** `OBJECT_STORAGE_SERVICE` (Supabase Storage / Google Cloud Storage)
- **PURPOSE:** Almacenar de forma segura PDFs generados, fotos de recepción, fotos de entrega (POD), firmas digitales y respaldos documentales.
- **BACKEND_ONLY:** `YES` (Los uploads y descargas son gestionados o autorizados mediante URLs firmadas temporales generadas por FastAPI).
- **SECRET_REQUIRED:** `YES` (Credenciales de servicio `service_role` o IAM Service Account privadas solo en backend).
- **FALLBACK_REQUIRED:** `NO` (Servicio crítico para persistencia de evidencias; reintentos con exponential backoff).
- **SOURCE_EVIDENCE_REQUIRED:** `YES` (Hash SHA-256 del archivo almacenado en base de datos para verificación de integridad).
- **PHASE_OWNER:** `F015`

---

### Integración 6: Servicio de Notificaciones y Mensajería (Notification Service)
- **NAME:** `NOTIFICATION_DISPATCH_SERVICE` (Email SMTP / SendGrid / WhatsApp / SMS)
- **PURPOSE:** Enviar confirmaciones de citas, alertas de despacho, códigos OTP de entrega y notificaciones de arribo al cliente.
- **BACKEND_ONLY:** `YES`
- **SECRET_REQUIRED:** `YES`
- **FALLBACK_REQUIRED:** `YES` (Registro en cola de reintentos asíncrona; el flujo operativo principal no se bloquea ante fallo en el envío).
- **SOURCE_EVIDENCE_REQUIRED:** `YES` (Log de despacho con message_id devuelto por el proveedor).
- **PHASE_OWNER:** `F074`
