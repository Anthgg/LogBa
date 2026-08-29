# Ambiente: Development (Desarrollo Local)

## Propósito
Entorno de desarrollo local para ingenieros de software, pruebas interactivas de componentes y desarrollo de nuevas funcionalidades.

## Variables de Configuración
| Variable | Valor Típico / Formato | Descripción |
|---|---|---|
| `APP_ENV` | `development` | Identifica el entorno de desarrollo |
| `APP_DEBUG` | `true` | Habilita logs detallados y mensajes de error descriptivos |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/postgres` | Conexión local / remota de desarrollo |
| `BACKEND_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Orígenes locales de Vite Frontend |
| `SESSION_COOKIE_SECURE` | `false` | Permite cookies sobre HTTP local (`localhost`) |
| `SESSION_COOKIE_SAMESITE` | `lax` | Política estándar para navegación local |
| `SESSION_COOKIE_HTTPONLY` | `true` | Protección contra acceso JavaScript a la cookie |
| `CSRF_SIGNING_SECRET` | Clave secreta local de 32+ caracteres | Firma criptográfica de tokens CSRF |
| `MFA_ENCRYPTION_KEY` | Clave AES-256-GCM en base64 de 32 bytes | Cifrado de secretos TOTP en reposo |
| `DEMO_USER_PASSWORD` | Contraseña configurada en `.env` | Contraseña para scripts de inicialización |

## Reglas Operativas
- **Datos Sintéticos**: PERMITIDOS (`is_test_data = true`).
- **Seed de Demostración**: Permitido mediante `python -m app.scripts.seed_demo`.
- **Cero Secretos en Git**: Todas las claves privadas y secretos deben residir exclusivamente en `.env` (ignorado por Git).
