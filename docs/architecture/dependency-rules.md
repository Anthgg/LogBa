# Reglas de Dependencia y Patrones Anti-Ciclos

Este documento establece las directrices de acoplamiento, dependencias entre módulos y el patrón de verificación de prerrequisitos del **Sistema Logístico Integral**.

---

## 1. Regla Anti-Ciclos Estricta

> **CIRCULAR_DOMAIN_DEPENDENCIES = 0**

1. Las dependencias entre dominios deben formar un **Grafo Acíclico Dirigido (DAG)**.
2. Quedan estrictamente prohibidas las importaciones mutuas o circulares entre módulos de negocio (ej. `inventory` importa `purchasing` y `purchasing` importa `inventory`).
3. Si dos dominios necesitan colaborar:
   - Se debe desacoplar la interacción mediante contratos explícitos, capas de servicio compartidas (`app/shared/`) o emisión de eventos.

---

## 2. Prohibición de God Services y God Utils

1. **No God Services:** Prohibido crear clases monolíticas como `LogisticsService` que orquesten indiscriminadamente compras, almacenes, inventario y rutas en un solo archivo. Cada dominio mantiene su propio ownership.
2. **No God Utils:** Prohibido el uso de archivos genéricos `utils.py` con cientos de funciones desconectadas. Las utilidades deben pertenecer a paquetes específicos con propósito único.

---

## 3. Patrón Dependency Gate (Prerrequisitos Operativos)

Toda operación que requiera recursos previos (ej. Recepción requiere Organización, Sede, Almacén y OC aprobada) debe implementar un **Dependency Gate** antes de ejecutar la lógica principal:

```python
# Patrón Conceptual de Dependency Gate
def ensure_operational_prerequisites(db: Session, branch_id: str, warehouse_id: str):
    warehouse = warehouse_repo.get_active_by_id(db, warehouse_id, branch_id)
    if not warehouse:
        raise DependencyRequiredError(
            message="El almacén especificado no existe o no se encuentra activo para esta sede.",
            code="WAREHOUSE_REQUIRED",
            details={"branch_id": branch_id, "warehouse_id": warehouse_id},
        )
```

- **Garantía:** El sistema responde siempre con un error de dominio tipado (`409 Conflict` / `422 Unprocessable Entity`), evitando fallos inesperados de integridad referencial o errores no controlados `500`.
