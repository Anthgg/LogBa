# Exclusiones Explícitas del Alcance Inicial

Este documento define formalmente los límites externos del **Sistema Logístico Integral**, detallando las áreas funcionales que **NO forman parte** del alcance inicial del proyecto para preservar el foco en la excelencia operativa logística y evitar sobrearquitectura.

---

## 1. Módulos y Capacidades Excluidas

### 1.1. Contabilidad General y Libros Electrónicos
- **Exclusión:** No se implementará un ERP contable ni generación de Libros Contables Oficiales (Libro Diario, Libro Mayor, Balances, Estados Financieros).
- **Límite:** El sistema gestiona valorizaciones de inventario y costos operativos logísticos, pero no genera asientos contables de partida doble ni balance general.

### 1.2. Facturación Electrónica SUNAT Completa (PSE / OSE)
- **Exclusión:** No se incluye la emisión directa y firma de XML de comprobantes tributarios (Factura, Boleta) como Proveedor de Servicios Electrónicos (PSE/OSE).
- **Límite:** El sistema genera Guías de Remisión internas, Manifiestos y Actas operativas. Las interfaces para emisión fiscal se contemplarán como integraciones futuras de exportación.

### 1.3. Planilla, Nómina y Gestión de Recursos Humanos
- **Exclusión:** No se gestiona cálculo de remuneraciones, retenciones, beneficios sociales, contratos laborales ni liquidaciones.
- **Límite:** El sistema administra exclusivamente perfiles operativos (conductores, operadores de almacén) con sus datos técnicos relevantes para la operación (licencias de conducir, roles y permisos).

### 1.4. Tesorería y Conciliación Bancaria
- **Exclusión:** No se incluyen cuentas bancarias, emisión de cheques, transferencias bancarias directas ni conciliación bancaria.
- **Límite:** Las órdenes de compra registran montos y condiciones de pago pactadas, pero la ejecución del pago financiero pertenece a sistemas externos.

### 1.5. CRM General, Redes Sociales y Marketing
- **Exclusión:** No se desarrollará gestión de leads de prospección comercial, campañas de marketing, gestión de redes sociales o marketing automation.
- **Límite:** Se mantiene un directorio maestro de Socios Comerciales (Clientes y Proveedores) con datos estrictamente logísticos y de contacto operativo.

### 1.6. Comercio Electrónico B2C y Pasarelas de Pago Directas
- **Exclusión:** No se construye una tienda online B2C (e-commerce marketplace) con carrito de compras público ni procesamiento de tarjetas de crédito (Stripe, MercadoPago, etc.).
- **Límite:** El sistema recibe y procesa pedidos de salida (Sales Orders) listos para su preparación y despacho físico.

### 1.7. Manufactura Pesada y Producción Industrial (MRP II)
- **Exclusión:** No se incluye planificación avanzada de líneas de ensamblaje industrial masivo ni diagramación de procesos de manufactura compleja.
- **Límite:** Se soporta ensamblaje ligero básico (Kitting/Bundling) para despacho promocional si fuera requerido.

### 1.8. Biometría Avanzada y Reconocimiento Facial por IA
- **Exclusión:** No se utilizará procesamiento de reconocimiento facial o huellas dactilares para control de acceso.
- **Límite:** La validación de entregas e ingresos se realiza mediante credenciales digitales seguras, firmas en pantalla táctil, códigos OTP y fotografías de respaldo.

---

## 2. Matriz de Decisión de Alcance

| Área Funcional | En Alcance Logístico | Sistema Destino / Externo |
| :--- | :---: | :--- |
| **Control de Stock y Kardex** | **SÍ (Core)** | Sistema Logístico Integral |
| **Ruteo y Despacho Físico** | **SÍ (Core)** | Sistema Logístico Integral |
| **Gestión de Compras y Recepción** | **SÍ (Core)** | Sistema Logístico Integral |
| **Generación de Asientos Contables** | **NO** | ERP Contable / Software Tributario |
| **Cálculo de Planilla / Nómina** | **NO** | Sistema de RRHH / Payroll |
| **Tienda B2C / Carrito Web** | **NO** | Plataforma de E-commerce |
| **Conciliación Bancaria** | **NO** | Sistema Financiero / Tesorería |
