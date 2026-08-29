# Arquitectura de Autenticación, Sesiones y Seguridad (F008)

El Sistema Logístico Integral implementa una arquitectura de identidad única gobernada de forma exclusiva por el backend en FastAPI y persistida en PostgreSQL/Supabase.

## Principios Fundamentales

1. **Autoridad Absoluta del Backend**: El backend es la única entidad que verifica credenciales, calcula hashes, gestiona sesiones y evalúa roles y permisos. El frontend en React es estrictamente una capa de presentación.
2. **Sin Tokens en Almacenamiento Local**: Prohibido almacenar tokens JWT, tokens de sesión o refresh tokens en `localStorage`, `sessionStorage` o `IndexedDB`.
3. **Cookies HttpOnly**: La sesión del usuario se transmite exclusivamente mediante una cookie `logistics_session` configurada con `HttpOnly=True`, `SameSite=Lax`, `Path=/` y `Secure=True` en producción.
4. **Almacenamiento de Tokens Hasheados**: La base de datos nunca almacena el token de sesión en texto plano, sino su hash SHA-256 (`token_hash`).
5. **Algoritmo de Hashing Argon2id**: Las contraseñas de los usuarios se procesan mediante `pwdlib` utilizando Argon2id con parámetros recomendados de la industria.
6. **Protección CSRF Firmada**: Las solicitudes mutadoras (`POST`, `PUT`, `PATCH`, `DELETE`) exigen el encabezado `X-CSRF-Token` con un token criptográficamente firmado mediante HMAC SHA-256 (`CSRF_SIGNING_SECRET`).
7. **Control de Acceso Basado en Permisos (RBAC F006)**: La autorización no se evalúa por nombre de rol sino por permisos efectivos asociados a los roles activos del usuario (`AuthenticatedPrincipal.has_permission(...)`).
8. **Trazabilidad de Auditoría Real (F007)**: Todas las operaciones autenticadas se registran con `actor_type="AUTHENTICATED"`, `actor_id=<UUID del usuario>` y `session_id=<UUID de la sesión>`.

## Ciclo de Vida de la Sesión

- **Login (`POST /api/auth/login`)**:
  1. Valida token CSRF.
  2. Normaliza el correo electrónico (`email.strip().lower()`).
  3. Verifica la contraseña con Argon2id contra `users.password_hash`.
  4. Genera un token aleatorio con 256 bits de entropía (`secrets.token_urlsafe(32)`).
  5. Almacena `sha256(raw_token)` en `auth_sessions`.
  6. Emite cookie `HttpOnly` y registra evento `auth.login` en auditoría.
- **Validación de Sesión (`GET /api/auth/me` / Dependencias de endpoints)**:
  1. Extrae token desde la cookie `logistics_session`.
  2. Valida expiración absoluta (`SESSION_ABSOLUTE_TTL_MINUTES`, por defecto 480 min).
  3. Valida tiempo de inactividad (`SESSION_IDLE_TIMEOUT_MINUTES`, por defecto 30 min).
  4. Valida que `revoked_at` sea `NULL` y que el usuario esté activo (`users.is_active=True`).
  5. Resuelve permisos efectivos y construye el objeto `AuthenticatedPrincipal`.
- **Logout (`POST /api/auth/logout`)**:
  1. Valida token CSRF.
  2. Marca `auth_sessions.revoked_at = now()`.
  3. Registra evento `auth.logout` en auditoría.
  4. Elimina la cookie `logistics_session` del navegador.

## Matriz de Códigos HTTP

- **401 Unauthorized (`AUTHENTICATION_REQUIRED` / `INVALID_CREDENTIALS` / `CSRF_TOKEN_INVALID`)**: Falta de sesión, sesión expirada, sesión revocada o credenciales incorrectas.
- **403 Forbidden (`PERMISSION_DENIED` / `ROLE_ORGANIZATION_MISMATCH`)**: Usuario autenticado sin el permiso requerido o intento de acceso entre organizaciones no autorizadas.
- **422 Unprocessable Content (`VALIDATION_ERROR` / `PASSWORD_TOO_SHORT`)**: Fallo de validación de esquema o política de contraseña (< 12 caracteres).
