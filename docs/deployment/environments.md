# Matriz de Ambientes

## Comparativa de Parámetros

| Atributo | Development | Test (CI) | Production |
|---|---|---|---|
| **Host** | Localhost (`127.0.0.1`) | GitHub Actions Runner | Google Cloud Run (`southamerica-west1`) |
| **`APP_ENV`** | `development` | `test` | `production` |
| **`APP_DEBUG`** | `true` | `true` | `false` |
| **Base de Datos** | Supabase Dev / Local Postgres | Contenedor Postgres Efímero | Supabase PostgreSQL Producción |
| **Aislamiento DB** | Separada | Separada y efímera | Segregación estricta |
| **Inyección de Secretos** | Archivo `.env` local | GitHub Actions Secrets / Env | Google Secret Manager |
| **Cookies Secure** | `false` (HTTP permitido) | `false` | `true` (HTTPS obligatorio) |
| **Cookie SameSite** | `lax` | `lax` | `none` (cross-origin) o `lax` |
| **Datos Sintéticos** | Permitidos | Permitidos | PROHIBIDOS (`0`) |
| **Auto Seed Demo** | Permitido bajo demanda | Permitido en suite de pruebas | PROHIBIDO (`PRODUCTION_AUTO_SEED = 0`) |
| **Almacenamiento Documental** | Local / Mock | Mock / Temp | Supabase Storage / GCS (F030) |
