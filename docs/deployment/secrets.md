# Gestión y Rotación de Secretos

## Catálogo de Secretos Productivos

| Nombre del Secreto en Secret Manager | Variable de Entorno | Propósito | Impacto de Rotación |
|---|---|---|---|
| `logba-database-url` | `DATABASE_URL` | String de conexión a PostgreSQL | Requiere restart de instancias Cloud Run |
| `logba-csrf-signing-secret` | `CSRF_SIGNING_SECRET` | Firma HMAC de tokens CSRF | Invalida tokens CSRF activos en clientes |
| `logba-mfa-encryption-key` | `MFA_ENCRYPTION_KEY` | Llave AES-256-GCM (32 bytes) para secretos TOTP en reposo | **CRÍTICO**: Rotación sin migración de datos imposibilita descifrar TOTP existentes |

## Procedimiento de Rotación Segura para `MFA_ENCRYPTION_KEY`
Si se requiere rotar la clave de cifrado MFA:
1. Añadir la nueva clave como versión activa en Secret Manager y mantener la anterior para descifrado transitorio.
2. Ejecutar un script administrativo backend que:
   - Lea cada registro de `user_mfa_factors`.
   - Descifre `secret_ciphertext` con la clave anterior.
   - Recifre con la nueva clave.
   - Actualice el registro atómicamente.
3. Desactivar la versión anterior en Secret Manager.
