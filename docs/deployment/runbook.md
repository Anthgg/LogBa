# Runbook de Operaciones e Incidentes

## 1. Flujo Canónico de Despliegue
1. **Validación CI**: Pasar todos los gates en GitHub Actions (`ruff`, `mypy`, `pytest`, `eslint`, `tsc`, `vite build`).
2. **Migración DB**: Ejecutar job de migración controlado si aplica (`alembic upgrade head`).
3. **Build & Deploy Backend**: Construir imagen con SHA exacto y desplegar a `logba-api`.
4. **Smoke Backend**: Verificar `GET /live`, `GET /ready` y `GET /api/auth/csrf`.
5. **Build & Deploy Frontend**: Construir imagen con `VITE_API_URL` del backend y desplegar a `fronlog-web`.
6. **Smoke Frontend**: Verificar `GET /` y flujo de autenticación en navegador.

## 2. Diagnóstico de Incidentes

### Incidente: Fallo de Conectividad a Base de Datos (503 Service Unavailable en `/ready`)
- **Síntoma**: `GET /ready` retorna `{"status": "error", "database": "disconnected"}`.
- **Acción**:
  1. Verificar estado de Supabase PostgreSQL y pool de conexiones.
  2. Verificar que el secreto `logba-database-url` en Secret Manager sea válido y tenga permisos de lectura para el Service Account de Cloud Run.
  3. Revisar logs estructurados con `gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="logba-api"' --limit=20`.

### Incidente: Error de Step-Up o Cifrado MFA (422 / 500 en TOTP)
- **Síntoma**: Fallo al desencriptar factores TOTP o verificar Step-Up challenges.
- **Acción**:
  1. Verificar que `MFA_ENCRYPTION_KEY` montado en Cloud Run coincida exactamente con la clave con la que fueron cifrados los factores.
  2. NUNCA rotar `MFA_ENCRYPTION_KEY` sin ejecutar el procedimiento de migración de claves en reposo (ver `secrets.md`).

### Incidente: Error de CORS o Cookies no persistidas en Navegador
- **Síntoma**: Peticiones desde el frontend fallan con bloqueo CORS o `/api/auth/me` retorna 401 tras iniciar sesión.
- **Acción**:
  1. Verificar que `BACKEND_CORS_ORIGINS` contenga la URL HTTPS exacta de `fronlog-web`.
  2. Verificar que `SESSION_COOKIE_SECURE=true` y `SESSION_COOKIE_SAMESITE=none` (para orígenes cruzados en `.run.app`).
