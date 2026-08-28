# Arquitectura Modular del Backend

Este documento describe la arquitectura modular, las capas internas de diseño, el flujo de datos y la administración de recursos en el **Sistema Logístico Integral**.

---

## 1. Visión General y Flujo de Arquitectura

El backend se estructura como una aplicación modular orientada a dominios con infraestructura y servicios compartidos claramente delimitados:

```text
CLIENTE (React / Frontend)
   ↓ HTTP Request (JSON)
FASTAPI ROUTER (app/api/...)
   ↓ DTOs / Schemas validados
DOMAIN SERVICE (app/modules/{domain}/services/...)
   ↓ Entidades / Filtros de dominio
REPOSITORY (app/modules/{domain}/repositories/...)
   ↓ Consultas SQLAlchemy 2.x
POSTGRESQL (Supabase) / STORAGE / EXTERNAL APIS
```

---

## 2. Capas Internas por Dominio (Layered Design)

Cada módulo funcional futuro implementará una separación estricta de responsabilidades:

1. **`router` (Capa de Transporte HTTP):**
   - Responsable únicamente de enrutamiento HTTP, códigos de estado, inyección de dependencias de sesión/usuario y serialización de respuestas con Schemas de Pydantic.
   - **Regla Estricta:** Cero sentencias SQL y cero reglas de negocio en los routers (`SQL_IN_ROUTERS = 0`, `BUSINESS_LOGIC_IN_ROUTERS = 0`).

2. **`service` (Capa de Lógica de Negocio y Dominio):**
   - Responsable de validar invariantes, estados permitidos, cálculos oficiales (impuestos, subtotales, inventario), orquestar repositorios y registrar auditoría.
   - Es independiente de la capa de transporte HTTP y de cualquier framework visual.

3. **`repository` (Capa de Persistencia y Acceso a Datos):**
   - Encapsula todas las operaciones de base de datos con SQLAlchemy (consultas, filtros, inserciones, actualizaciones y bloqueos de fila `SELECT FOR UPDATE`).
   - **Regla Estricta:** Desconoce por completo peticiones HTTP, cabeceras o formatos de presentación (`HTTP_LOGIC_IN_REPOSITORIES = 0`).

4. **`schemas` (Contratos de Datos / DTOs):**
   - Define modelos Pydantic para validación de entrada (`CreateRequest`, `UpdateRequest`, `FilterParams`) y salida (`ResponseDTO`, `DetailDTO`).

5. **`models` (Mapeo Objeto-Relacional ORM):**
   - Define tablas y relaciones SQLAlchemy que mapean las estructuras en PostgreSQL.

---

## 3. Administración Centralizada del Engine y Sesión de Base de Datos

- **Un Solo Engine Central:** El sistema opera bajo una única configuración centralizada de SQLAlchemy Engine en `app/db/connection.py` (`DUPLICATE_DATABASE_ENGINES = 0`).
- **Ciclo de Vida de la Sesión:** La sesión de base de datos se inyecta por solicitud utilizando el generador `get_db()` de FastAPI (`yield db`), garantizando el cierre automático y liberación de conexiones al pool al finalizar la petición.
