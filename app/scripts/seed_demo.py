from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.connection import SessionLocal
from app.modules.organization.models import (
    Branch,
    OperationalLocation,
    Organization,
    Role,
    Warehouse,
)
from app.modules.organization.repository import (
    BranchRepository,
    OperationalLocationRepository,
    OrganizationRepository,
    RoleRepository,
    WarehouseRepository,
)

settings = get_settings()


def run_seed() -> None:
    if settings.is_production:
        print("CRITICAL ERROR: Seed script cannot be run in production environment.")
        raise RuntimeError("CRITICAL ERROR: Cannot seed test data in production environment.")

    db: Session = SessionLocal()
    org_repo = OrganizationRepository()
    branch_repo = BranchRepository()
    wh_repo = WarehouseRepository()
    loc_repo = OperationalLocationRepository()
    role_repo = RoleRepository()

    try:
        # --- 1. Canonical System Roles ---
        system_roles = [
            (
                "SUPER_ADMIN",
                "Administrador Global del Sistema",
                "Acceso total a todas las funciones y configuraciones globales",
            ),
            (
                "LOGISTICS_ADMIN",
                "Administrador General de Logística",
                "Gestión operativa integral de sedes, inventarios y despachos",
            ),
            (
                "WAREHOUSE_SUPERVISOR",
                "Supervisor de Almacén",
                "Control de ingresos, salidas, inventarios y operarios de almacén",
            ),
            (
                "WAREHOUSE_OPERATOR",
                "Operador de Almacén",
                "Ejecución de picking, packing, conteo y recepción física",
            ),
            (
                "PURCHASING_OFFICER",
                "Encargado de Compras",
                "Gestión de órdenes de compra, proveedores y abastecimiento",
            ),
            (
                "TRANSPORT_COORDINATOR",
                "Coordinador de Transporte",
                "Planificación de rutas, asignación de vehículos y monitoreo",
            ),
            (
                "DRIVER",
                "Conductor / Transportista",
                "Ejecución de entregas y confirmación de recepción en campo",
            ),
            (
                "AUDITOR",
                "Auditor Técnico y de Control",
                "Inspección de trazabilidad, auditoría y revisión de kardex",
            ),
        ]

        for code, name, desc in system_roles:
            existing_sys_role = role_repo.get_by_code(db, code, organization_id=None)
            if not existing_sys_role:
                sys_role = Role(
                    code=code,
                    name=name,
                    description=desc,
                    organization_id=None,
                    is_system=True,
                    is_active=True,
                    is_test_data=False,
                )
                role_repo.create(db, sys_role)
                print(f"System Role created: {code}")

        # --- 2. Demo Organization ---
        demo_org = org_repo.get_by_code(db, "DEMO-ORG-001")
        if not demo_org:
            demo_org = Organization(
                code="DEMO-ORG-001",
                name="Organización Logística Demo",
                is_active=True,
                is_test_data=True,
            )
            org_repo.create(db, demo_org)
            db.flush()
            print(f"Demo Organization created: {demo_org.code} ({demo_org.id})")

        # --- 3. Demo Custom Role ---
        custom_role = role_repo.get_by_code(db, "DEMO-ROLE-QC", organization_id=demo_org.id)
        if not custom_role:
            custom_role = Role(
                code="DEMO-ROLE-QC",
                name="Inspector de Control de Calidad Demo",
                description="Rol para inspección de lotes y calidad de productos",
                organization_id=demo_org.id,
                is_system=False,
                is_active=True,
                is_test_data=True,
            )
            role_repo.create(db, custom_role)
            print(f"Demo Custom Role created: {custom_role.code}")

        # --- 4. Branch 1: Lima ---
        branch_lim = branch_repo.get_by_code(db, demo_org.id, "DEMO-LIM")
        if not branch_lim:
            loc_lim = OperationalLocation(
                label="Sede Central Lima",
                address_line1="Av. Argentina 2450",
                district="Cercado de Lima",
                province="Lima",
                department="Lima",
                country_code="PE",
                latitude=-12.046374,
                longitude=-77.042793,
            )
            loc_repo.create(db, loc_lim)
            db.flush()

            branch_lim = Branch(
                organization_id=demo_org.id,
                code="DEMO-LIM",
                name="Sede Central Lima",
                location_id=loc_lim.id,
                is_active=True,
                is_test_data=True,
            )
            branch_repo.create(db, branch_lim)
            db.flush()
            print(f"Demo Branch created: {branch_lim.code}")

            # Warehouse 1 (shared location)
            wh1 = Warehouse(
                organization_id=demo_org.id,
                branch_id=branch_lim.id,
                code="DEMO-LIM-ALM-01",
                name="Almacén Principal Lima",
                location_id=loc_lim.id,
                is_active=True,
                is_test_data=True,
            )
            wh_repo.create(db, wh1)
            print(f"Demo Warehouse created: {wh1.code} (shared location)")

            # Warehouse 2 (independent location)
            loc_wh2 = OperationalLocation(
                label="Almacén Secundario Callao",
                address_line1="Av. Elmer Faucett 3100",
                district="Callao",
                province="Callao",
                department="Callao",
                country_code="PE",
                latitude=-12.023456,
                longitude=-77.108921,
            )
            loc_repo.create(db, loc_wh2)
            db.flush()

            wh2 = Warehouse(
                organization_id=demo_org.id,
                branch_id=branch_lim.id,
                code="DEMO-LIM-ALM-02",
                name="Almacén Secundario Callao",
                location_id=loc_wh2.id,
                is_active=True,
                is_test_data=True,
            )
            wh_repo.create(db, wh2)
            print(f"Demo Warehouse created: {wh2.code} (custom location)")

        # --- 5. Branch 2: Arequipa ---
        branch_aqp = branch_repo.get_by_code(db, demo_org.id, "DEMO-AQP")
        if not branch_aqp:
            loc_aqp = OperationalLocation(
                label="Sede Regional Sur Arequipa",
                address_line1="Parque Industrial Mz. G Lote 12",
                district="Cerro Colorado",
                province="Arequipa",
                department="Arequipa",
                country_code="PE",
                latitude=-16.378912,
                longitude=-71.554231,
            )
            loc_repo.create(db, loc_aqp)
            db.flush()

            branch_aqp = Branch(
                organization_id=demo_org.id,
                code="DEMO-AQP",
                name="Sede Regional Arequipa",
                location_id=loc_aqp.id,
                is_active=True,
                is_test_data=True,
            )
            branch_repo.create(db, branch_aqp)
            db.flush()
            print(f"Demo Branch created: {branch_aqp.code}")

            wh_aqp = Warehouse(
                organization_id=demo_org.id,
                branch_id=branch_aqp.id,
                code="DEMO-AQP-ALM-01",
                name="Almacén Regional Arequipa",
                location_id=loc_aqp.id,
                is_active=True,
                is_test_data=True,
            )
            wh_repo.create(db, wh_aqp)
            print(f"Demo Warehouse created: {wh_aqp.code} (shared location)")

        db.commit()
        print("Demo seed completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
