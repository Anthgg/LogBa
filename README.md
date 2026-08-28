# Sistema Logístico Integral - Backend API

Backend del Sistema Logístico Integral construido con **FastAPI**, **SQLAlchemy 2.x**, **Pydantic Settings** y **PostgreSQL (Supabase)**.

## REGLAS DE ORO DEL PROYECTO (F001 — F100)

### 1. Backend como Única Autoridad
1. **Frontend nunca accede directamente a DB:** Todas las operaciones pasan por FastAPI.
2. **Frontend nunca consume APIs externas de negocio:** El backend orquesta e integra servicios externos.
3. **Frontend nunca contiene secretos:** Credenciales, llaves privadas y tokens administrativos viven solo en backend.
4. **Backend ejecuta reglas y cálculos:** Precios, impuestos, costos, stock, kardex y conversiones son calculados por el backend.
5. **Backend genera documentos:** PDFs, Excel, CSVs y etiquetas son generados en backend.
6. **Backend controla persistencia:** Transacciones, integridad y modelos residen en backend.
7. **Backend es autoridad de permisos:** Autorización estricta por identidad, organización, sede y rol en cada endpoint.
8. **Frontend solamente consume contratos API:** Capa pura de presentación e interacción.

### 2. Datos Sintéticos Realistas (Zero Empty Screens & Real Architecture Flow)
1. **Recorrido Real:** Los datos de prueba atraviesan toda la arquitectura: `Seed/Backend -> PostgreSQL -> FastAPI -> Frontend UI`.
2. **Prohibido Mocking en Frontend:** Cero arrays u objetos hardcodeados en cliente para simular operatividad.
3. **Protección de Producción:** Los datos sintéticos están permitidos en `development`, `test` y `staging`, pero **estrictamente prohibidos** en `production` (`FAKE_OPERATIONAL_DATA_IN_PRODUCTION = 0`).

## Documentación de Arquitectura y Alcance

La definición formal del alcance, límites y contratos del sistema se encuentra en [`docs/scope/`](docs/scope/):
- [Alcance Logístico Detallado](docs/scope/logistics-scope.md)
- [Límites de Módulos](docs/scope/module-boundaries.md)
- [Exclusiones Explícitas del Sistema](docs/scope/exclusions.md)
- [Marco de Integraciones Externas](docs/scope/external-integrations.md)
- [Matriz de Responsabilidades API ↔ UI](docs/scope/api-ui-responsibilities.md)
- [Política de Datos Sintéticos Realistas](docs/scope/synthetic-data-policy.md)

## Requisitos Técnicos

- **Versión Canónica de Python:** Python 3.12
- PostgreSQL en Supabase

## Configuración del Entorno

1. Copiar el archivo de plantilla `.env.example` a `.env`:
   ```bash
   cp .env.example .env
   ```
2. Configurar las variables en `.env`:
   - `DATABASE_URL`: Cadena de conexión PostgreSQL de Supabase (`postgresql+psycopg://...`).
   - `SUPABASE_URL`: URL del proyecto Supabase (`https://...`).
   - `SUPABASE_ANON_KEY`: Llave pública/anon de Supabase.
   - `SUPABASE_SERVICE_ROLE_KEY`: Llave administrativa secreta (opcional, backend-only).
   - `BACKEND_CORS_ORIGINS`: Orígenes permitidos (por defecto `http://localhost:5173`).

> **Seguridad**: El archivo `.env` contiene credenciales sensibles y está estrictamente ignorado por `.gitignore`. NUNCA versionar ni compartir archivos `.env`.

## Instalación y Ejecución

```bash
# Crear y activar entorno virtual con Python 3.12
python -m venv .venv
# En Windows PowerShell:
.venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar el servidor de desarrollo
uvicorn app.main:app --reload --port 8000
```

## Calidad de Código y Pruebas

```bash
# Linter con Ruff
ruff check .

# Formateo con Ruff
ruff format --check .

# Type checking con Mypy
mypy app

# Ejecutar suite de pruebas
pytest -v
```

## Endpoints Técnicos y de Salud

- `GET /live`: Liveness probe (devuelve `{"status": "ok"}`).
- `GET /ready`: Readiness probe (verifica la conexión real con Supabase PostgreSQL ejecutando `SELECT 1`).
- `GET /api/system/info`: Información pública técnica del sistema para validación de integración Frontend-Backend.
