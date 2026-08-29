# Ambiente: Production (Cloud Run & Supabase PostgreSQL)

## Propósito
Entorno operativo real para usuarios finales y procesos de negocio de la organización logística.

## Variables de Configuración
| Variable | Fuente de Configuración | Descripción |
|---|---|---|
| `APP_ENV` | Variable de Entorno Cloud Run (`production`) | Modo productivo |
| `APP_DEBUG` | Variable de Entorno Cloud Run (`false`) | Deshabilita trazas de error y detalles internos |
| `PORT` | Variable inyectada por Cloud Run (`8080` / `$PORT`) | Puerto HTTP del contenedor |
| `DATABASE_URL` | Secret Manager (`logba-database-url:latest`) | Conexión segura a Supabase PostgreSQL |
| `BACKEND_CORS_ORIGINS` | Variable de Entorno Cloud Run | URLs exactas del Frontend productivo en Cloud Run |
| `SESSION_COOKIE_SECURE` | Variable de Entorno Cloud Run (`true`) | Exige HTTPS para transmisión de cookies de sesión |
| `SESSION_COOKIE_SAMESITE` | Variable de Entorno Cloud Run (`none` o `lax`) | Política cross-origin sobre HTTPS |
| `SESSION_COOKIE_HTTPONLY` | Variable de Entorno Cloud Run (`true`) | Bloqueo estricto de acceso JavaScript a cookies |
| `CSRF_SIGNING_SECRET` | Secret Manager (`logba-csrf-signing-secret:latest`) | Clave criptográfica HMAC-SHA256 para CSRF |
| `MFA_ENCRYPTION_KEY` | Secret Manager (`logba-mfa-encryption-key:latest`) | Clave AES-256-GCM persistente para TOTP |
| `DEMO_USER_PASSWORD` | NO DEFINIDA | Prohibido en producción |

## Reglas Operativas (Regla de Oro 2)
- **Cero Datos Sintéticos**: `FAKE_OPERATIONAL_DATA_IN_PRODUCTION = 0`.
- **Cero Auto-Seeds**: `PRODUCTION_AUTO_SEED = 0`. No se ejecutan seeds automáticos de demo al arrancar el contenedor.
- **Desacoplamiento de Migraciones**: Las migraciones `alembic upgrade head` se ejecutan mediante un paso previo de migración y NUNCA en el inicio de la app (`MIGRATION_ON_APP_STARTUP = 0`).
- **Cero Secretos en Repositorio**: Todo secreto reside en Google Secret Manager.
