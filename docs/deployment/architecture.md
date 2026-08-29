# Arquitectura de Despliegue en Google Cloud

```
+-----------------------------------------------------------------------------------+
|                                Google Cloud Platform                              |
|                              (Region: southamerica-west1)                         |
|                                                                                   |
|  +---------------------------+             +----------------------------------+   |
|  |     Frontend Cloud Run    |   HTTPS     |        Backend Cloud Run         |   |
|  |       (fronlog-web)       | ----------> |           (logba-api)            |   |
|  |  [Nginx SPA + React Dist] |             |     [FastAPI + Python 3.12]      |   |
|  +---------------------------+             +-----------------+----------------+   |
|                                                              |                    |
|                                            +-----------------+-----------------+  |
|                                            |                 |                 |  |
|                                            v                 v                 v  |
|                             +--------------------+ +--------------------+ +----+--|
|                             |   Secret Manager   | | Artifact Registry  | | Cloud |
|                             | - logba-db-url     | |  (Docker Images)   | | Logging
|                             | - logba-csrf-sec   | |                    | | (JSON)|
|                             | - logba-mfa-key    | |                    | |       |
|                             +--------------------+ +--------------------+ +----+--|
+-----------------------------------------------------------------------------------+
                                             |
                                             v (TLS SSL Connection)
                              +-------------------------------+
                              |      Supabase PostgreSQL      |
                              |  - Schema 0006_f009           |
                              |  - Append-Only Audit Trail    |
                              |  - RBAC & Encrypted MFA State |
                              +-------------------------------+
```

## Componentes
1. **Frontend Service (`fronlog-web`)**:
   - Servidor HTTP Nginx ligero montado en Google Cloud Run.
   - Enrutamiento SPA con fallback `/index.html`.
   - Comunicación hacia la API mediante HTTPS y cookies seguras.
2. **Backend Service (`logba-api`)**:
   - Servidor FastAPI corriendo sobre Uvicorn en Google Cloud Run.
   - Probes `/live` (Liveness) y `/ready` (Readiness).
   - Inyección de secretos en tiempo de ejecución vía Secret Manager.
3. **Secret Manager**:
   - Almacenamiento criptográfico centralizado de `DATABASE_URL`, `CSRF_SIGNING_SECRET` y `MFA_ENCRYPTION_KEY`.
4. **Supabase PostgreSQL**:
   - Base de datos relacional PostgreSQL con extensiones UUID, encriptación AES-256-GCM para secretos MFA y auditoría append-only inmutable.
