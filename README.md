# Sistema Logístico Integral - Backend API

Backend del Sistema Logístico Integral construido con **FastAPI**, **SQLAlchemy 2.x**, **Pydantic Settings** y **PostgreSQL (Supabase)**.

## ARCHITECTURE GOLDEN RULE

1. **Frontend nunca accede directamente a DB:** Todas las operaciones pasan por FastAPI.
2. **Frontend nunca consume APIs externas de negocio:** El backend orquesta e integra servicios externos.
3. **Frontend nunca contiene secretos:** Credenciales, llaves privadas y tokens administrativos viven solo en backend.
4. **Backend ejecuta reglas y cálculos:** Precios, impuestos, costos, stock, kardex y conversiones son calculados por el backend.
5. **Backend genera documentos:** PDFs, Excel, CSVs y etiquetas son generados en backend.
6. **Backend controla persistencia:** Transacciones, integridad y modelos residen en backend.
7. **Backend es autoridad de permisos:** Autorización estricta por identidad, organización, sede y rol en cada endpoint.
8. **Frontend solamente consume contratos API:** Capa pura de presentación e interacción.

## Requisitos Previos

- Python >= 3.11
- PostgreSQL en Supabase

## Configuración del Entorno

1. Copiar el archivo de plantilla `.env.example` a `.env`:
   ```bash
   cp .env.example .env
   ```
2. Configurar las variables en `.env`:
   - `DATABASE_URL`: Cadena de conexión PostgreSQL de Supabase.
   - `SUPABASE_URL`: URL del proyecto Supabase.
   - `SUPABASE_ANON_KEY`: Llave pública/anon de Supabase.
   - `SUPABASE_SERVICE_ROLE_KEY`: Llave administrativa secreta (opcional, backend-only).

> **Seguridad**: El archivo `.env` contiene credenciales sensibles y está estrictamente ignorado por `.gitignore`. NUNCA versionar ni compartir archivos `.env`.

## Instalación y Ejecución

```bash
# Crear y activar entorno virtual
python -m venv .venv
# En Windows PowerShell:
.venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar el servidor de desarrollo
uvicorn app.main:app --reload --port 8000
```

## Endpoints de Salud (Health Checks)

- `GET /live`: Liveness probe (devuelve `{"status": "ok"}`).
- `GET /ready`: Readiness probe (verifica la conexión real con Supabase PostgreSQL ejecutando `SELECT 1`).
