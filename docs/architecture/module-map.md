# Mapa Canónico de Módulos (Module Map)

Este documento detalla la matriz canónica de los **15 Módulos de Dominio** del **Sistema Logístico Integral**, sus dependencias ascendentes y sus servicios compartidos asociados.

---

| # | Módulo (`app/modules/`) | Responsabilidad Principal | Fases Objetivo | Dependencias de Dominio | Servicios Compartidos |
| :-: | :--- | :--- | :---: | :--- | :--- |
| **1** | `organization` | Organizaciones, Sedes y Multi-tenancy | `F004` | Ninguna (Raíz) | `audit` |
| **2** | `warehouse` | Almacenes, Zonas y Topología de Ubicaciones | `F004`, `F022` | `organization` | `audit` |
| **3** | `catalog` | Catálogo de Productos, Categorías y SKUs | `F024` | `organization` | `audit`, `files` |
| **4** | `business_partners`| Proveedores, Clientes y Homologación | `F025` | `organization` | `audit`, `integrations/ruc` |
| **5** | `purchasing` | Requerimientos, RFQs y Órdenes de Compra | `F031-F035` | `organization`, `catalog`, `business_partners` | `audit`, `documents` |
| **6** | `receiving` | Citas, Garita, Descarga y Control de Discrepancias | `F036-F040` | `warehouse`, `purchasing`, `business_partners` | `audit`, `documents`, `files` |
| **7** | `quality` | Inspecciones Técnicas y Liberación de Cuarentena | `F038` | `receiving`, `catalog` | `audit`, `files` |
| **8** | `inventory` | Kardex Inmutable, Lotes, Series, Putaway y Conteos | `F041-F050` | `warehouse`, `catalog`, `receiving` | `audit`, `documents` |
| **9** | `outbound` | Pedidos de Salida, Olas de Picking, Packing y Despacho | `F051-F060` | `inventory`, `catalog`, `business_partners` | `audit`, `documents` |
| **10**| `transport` | Vehículos, Conductores, Transportistas y Hojas de Ruta | `F061-F064` | `organization` | `audit`, `integrations/vehicle` |
| **11**| `routing` | Geocodificación y Optimización de Rutas Viales | `F065-F070` | `transport`, `business_partners` | `shared/routing` |
| **12**| `delivery` | Ejecución de Paradas, POD, Firmas, Fotos y OTP | `F071-F075` | `routing`, `outbound` | `audit`, `shared/files`, `documents` |
| **13**| `reverse_logistics`| Solicitudes RMA, Recojo, Reingreso y Scrap | `F076-F080` | `delivery`, `inventory`, `catalog` | `audit`, `documents`, `files` |
| **14**| `documents` | Configuración de Talonarios, Series y Correlativos | `F011-F020` | `organization` | `shared/documents` |
| **15**| `analytics` | Consolidación y Cálculo de KPIs Logísticos | `F081-F090` | Todos los dominios operacionales | `shared/documents` |
