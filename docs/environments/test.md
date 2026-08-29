# Ambiente: Test (CI & Automatización)

## Propósito
Entorno automatizado para integración continua (GitHub Actions) y ejecución de pruebas unitarias, de integración, RBAC, auditoría y MFA.

## Variables de Configuración
| Variable | Valor Típico / Formato | Descripción |
|---|---|---|
| `APP_ENV` | `test` | Modo de pruebas para desactivar logging ruidoso y optimizar tests |
| `APP_DEBUG` | `true` | Habilita detalles para diagnóstico de fallos en CI |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgrespassword@localhost:5432/postgres` | Base de datos efímera en contenedor Docker de CI |
| `BACKEND_CORS_ORIGINS` | `http://localhost:5173` | Orígenes mock de prueba |
| `SESSION_COOKIE_SECURE` | `false` | Permite pruebas de cookies en TestClient HTTP |
| `SESSION_COOKIE_SAMESITE` | `lax` | Política estándar para suite de pruebas |
| `SESSION_COOKIE_HTTPONLY` | `true` | Validación de atributos de seguridad en sesión |
| `CSRF_SIGNING_SECRET` | Clave temporal generada por el pipeline de CI | Firma de tokens en pruebas de CSRF |
| `MFA_ENCRYPTION_KEY` | Clave AES-256-GCM efímera de CI | Cifrado de factores TOTP en tests |

## Reglas Operativas
- **Aislamiento Total de Producción**: NUNCA conectar a la base de datos de producción durante las pruebas (`TEST_PROD_DATABASE_SEPARATION = PASS`).
- **Base de Datos Efímera**: Se crea y destruye en cada ejecución del workflow de GitHub Actions.
- **Datos Sintéticos**: PERMITIDOS para fixtures y escenarios de prueba (`is_test_data = true`).
