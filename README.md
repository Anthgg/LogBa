# Sistema Logístico Integral - Backend API

Backend del Sistema Logístico Integral construido con **FastAPI**, **SQLAlchemy 2.x**, **Pydantic Settings** y **PostgreSQL (Supabase)**.

## Requisitos Previos

- Python >= 3.11
- PostgreSQL en Supabase

## Configuración del Entorno

1. Copiar el archivo de plantilla `.env.example` a `.env`:
   ```bash
   cp .env.example .env
   ```
2. Configurar las variables en `.env`:
   - `DATABASE_URL`: Cadena de conexión PostgreSQL proporcionada por Supabase (ej. `postgresql+psycopg://postgres:[PASSWORD]@[HOST]:[PORT]/postgres`).
   - `SUPABASE_URL`: URL del proyecto Supabase.
   - `SUPABASE_ANON_KEY`: Llave pública anon de Supabase.

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
