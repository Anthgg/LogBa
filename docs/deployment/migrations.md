# Pipeline de Migraciones y Estrategia Zero-Downtime

## Principios Fundamentales
1. **Desacoplamiento de Arranque**: Las migraciones NUNCA se ejecutan en el `ENTRYPOINT` o arranque del contenedor Cloud Run (`MIGRATION_ON_APP_STARTUP = 0`).
2. **Validación de Cabezas**: El pipeline verifica que exista exactamente `1 HEAD` antes de proceder (`alembic heads`).
3. **Estrategia Expand-Contract**:
   - **Paso 1 (Expand)**: Añadir columnas o tablas nuevas como nulables o con valores por defecto.
   - **Paso 2 (Deploy App)**: Desplegar la nueva versión del backend compatible con la nueva y la vieja estructura.
   - **Paso 3 (Contract)**: Una vez estabilizado el backend, aplicar la migración que remueve columnas en desuso o restringe nulabilidad.

## Ejecución Controlada
```bash
# Comprobar estado previo
alembic current
alembic heads

# Aplicar migración
alembic upgrade head

# Confirmar revisión final
alembic current
```
