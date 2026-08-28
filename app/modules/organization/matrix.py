from typing import Dict, List

from app.modules.organization.schemas import (
    RoleMatrixResponse,
    RoleResponsibilityItem,
    SodConflictItem,
)

CANONICAL_RESPONSIBILITIES: Dict[str, Dict] = {
    "PURCHASING": {
        "name": "Encargado de Compras y Abastecimiento",
        "scope": "Adquisiciones y Proveedores",
        "responsibilities": [
            "Gestión de requerimientos y solicitudes de compra",
            "Cotizaciones y evaluación de proveedores",
            "Generación y seguimiento de órdenes de compra",
            "Negociación de términos de entrega y acuerdos comerciales",
        ],
    },
    "RECEIVING": {
        "name": "Especialista de Recepción y Descarga",
        "scope": "Muelle de Ingreso y Recepción",
        "responsibilities": [
            "Llegada y descarga física de unidades de transporte",
            "Cotejo físico contra órdenes de compra y guías de remisión",
            "Registro de diferencias, faltantes y mermas iniciales",
            "Ingreso formal de bultos a zona de recepción previa a calidad",
        ],
    },
    "QUALITY": {
        "name": "Inspector de Control de Calidad y Cuarentena",
        "scope": "Evaluación Técnica y Cuarentena",
        "responsibilities": [
            "Muestreo e inspección técnica de mercadería recibida",
            "Gestión de estado de cuarentena y aislamiento de lotes",
            "Evaluación de conformidad según fichas técnicas y normativas",
            "Dictamen formal de aprobación, observación o rechazo",
        ],
    },
    "WAREHOUSE": {
        "name": "Operador de Almacén y Putaway",
        "scope": "Operación Física de Almacén",
        "responsibilities": [
            "Ubicación física (putaway) y almacenamiento en racks/bahías",
            "Ejecución de picking y preparación de pedidos según orden",
            "Reabastecimiento de zonas de picking y traslados internos",
            "Mantenimiento del orden físico y seguridad del almacén",
        ],
    },
    "INVENTORY": {
        "name": "Controlador de Inventarios y Stock",
        "scope": "Control y Conciliación de Stock",
        "responsibilities": [
            "Monitoreo continuo de niveles de stock y disponibilidad",
            "Planificación y ejecución de conteos cíclicos y generales",
            "Conciliación de kardex y trazabilidad de movimientos",
            "Gestión de transferencias entre almacenes y solicitud de ajustes",
        ],
    },
    "DISPATCH": {
        "name": "Coordinador de Despacho y Packing",
        "scope": "Muelle de Salida y Despacho",
        "responsibilities": [
            "Consolidación y verificación de pedidos preparados",
            "Packing, embalaje, rotulado y pesaje de bultos",
            "Emisión y control de actas de despacho y guías de remisión",
            "Carga en vehículos de transporte y liberación operativa",
        ],
    },
    "TRANSPORT": {
        "name": "Planificador de Transporte y Rutas",
        "scope": "Planificación Logística de Transporte",
        "responsibilities": [
            "Planificación y optimización de rutas de distribución",
            "Cubicaje y asignación de unidades de transporte vehicular",
            "Asignación de conductores y cronogramas de despacho",
            "Monitoreo de tiempos de tránsito y rendimiento de flota",
        ],
    },
    "DRIVER": {
        "name": "Conductor y Transportista",
        "scope": "Operación en Ruta y Entrega",
        "responsibilities": [
            "Conducción segura de unidad de transporte asignada",
            "Monitoreo GPS y reporte de paradas o desvíos en ruta",
            "Entrega física en punto de destino / cliente final",
            "Confirmación de recepción con firma y recolección de evidencias",
        ],
    },
    "AUDITOR": {
        "name": "Auditor Técnico y de Trazabilidad",
        "scope": "Inspección y Cumplimiento Normativo",
        "responsibilities": [
            "Inspección independiente de trazabilidad y kardex",
            "Revisión de bitácoras de auditoría y registros inmutables",
            "Verificación de cumplimiento de políticas de segregación (SoD)",
            "Emisión de informes de control sin mutación operativa directa",
        ],
    },
    "MANAGEMENT": {
        "name": "Gerencia y Dirección Logística",
        "scope": "Supervisión Estratégica y Dirección",
        "responsibilities": [
            "Supervisión integral de KPIs de cadena de suministro",
            "Aprobación de políticas operativas y umbrales presupuestarios",
            "Autorización de operaciones críticas y excepciones escaladas",
            "Dirección estratégica y asignación de recursos globales",
        ],
    },
}

SOD_CONFLICTS_DATA: List[Dict[str, str]] = [
    {
        "role_a": "PURCHASING",
        "role_b": "RECEIVING",
        "conflict_level": "HIGH_RISK",
        "reason": (
            "Riesgo de compras fraudulentas con recepción ficticia "
            "de mercadería sin verificación independiente."
        ),
        "policy": (
            "Separación estricta obligatoria. Quien emite la orden "
            "de compra no puede firmar la recepción física."
        ),
    },
    {
        "role_a": "PURCHASING",
        "role_b": "MANAGEMENT",
        "conflict_level": "REVIEW_REQUIRED",
        "reason": "Concentración de poder de compra y aprobación presupuestaria.",
        "policy": (
            "Órdenes de compra generadas por gerencia requieren "
            "doble aprobación o auditoría independiente."
        ),
    },
    {
        "role_a": "RECEIVING",
        "role_b": "QUALITY",
        "conflict_level": "REVIEW_REQUIRED",
        "reason": (
            "Riesgo de aceptar y liberar mercancía no conforme para cumplir cuotas de recepción."
        ),
        "policy": (
            "El dictamen de calidad debe ser emitido por inspectores "
            "independientes del equipo de descarga."
        ),
    },
    {
        "role_a": "WAREHOUSE",
        "role_b": "INVENTORY",
        "conflict_level": "HIGH_RISK",
        "reason": (
            "El custodio físico del inventario no debe tener la "
            "potestad de ajustar saldos de stock para ocultar faltantes."
        ),
        "policy": (
            "Los conteos y conciliaciones deben ser validados "
            "por un controlador de inventario independiente."
        ),
    },
    {
        "role_a": "WAREHOUSE",
        "role_b": "DISPATCH",
        "conflict_level": "REVIEW_REQUIRED",
        "reason": (
            "Riesgo de salidas no autorizadas si el mismo operador "
            "prepara el pedido y libera la carga en muelle."
        ),
        "policy": "Doble verificación obligatoria en punto de packing y control de despacho.",
    },
    {
        "role_a": "INVENTORY",
        "role_b": "AUDITOR",
        "conflict_level": "HIGH_RISK",
        "reason": (
            "Pérdida de independencia si el auditor participa "
            "en los ajustes de stock que luego debe fiscalizar."
        ),
        "policy": (
            "El auditor tiene acceso exclusivo de solo lectura "
            "e inspección; no puede registrar ajustes de stock."
        ),
    },
    {
        "role_a": "DISPATCH",
        "role_b": "AUDITOR",
        "conflict_level": "HIGH_RISK",
        "reason": (
            "Conflicto de interés en la conciliación de salidas versus actas de entrega en destino."
        ),
        "policy": "Auditoría independiente de guías de remisión y actas de despacho.",
    },
    {
        "role_a": "TRANSPORT",
        "role_b": "DRIVER",
        "conflict_level": "REVIEW_REQUIRED",
        "reason": (
            "Riesgo de autoasignación de rutas preferenciales "
            "o manipulación de liquidación de viajes y viáticos."
        ),
        "policy": (
            "El planificador de transporte no debe operar como "
            "conductor en las mismas rutas que planifica."
        ),
    },
    {
        "role_a": "MANAGEMENT",
        "role_b": "AUDITOR",
        "conflict_level": "HIGH_RISK",
        "reason": (
            "Riesgo de anulación o encubrimiento de hallazgos "
            "de auditoría e interferencia en el canal de control."
        ),
        "policy": (
            "El canal de auditoría debe mantener reporte independiente "
            "con registro inmutable de bitácora."
        ),
    },
]


def get_canonical_matrix_data() -> RoleMatrixResponse:
    profiles = [
        RoleResponsibilityItem(
            role_code=code,
            role_name=data["name"],
            responsibilities=data["responsibilities"],
            operational_scope=data["scope"],
        )
        for code, data in CANONICAL_RESPONSIBILITIES.items()
    ]
    conflicts = [
        SodConflictItem(
            role_a=c["role_a"],
            role_b=c["role_b"],
            conflict_level=c["conflict_level"],
            reason=c["reason"],
            policy=c["policy"],
        )
        for c in SOD_CONFLICTS_DATA
    ]
    return RoleMatrixResponse(canonical_profiles=profiles, sod_conflicts=conflicts)
