from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.connection import SessionLocal
from app.modules.auth.models import User
from app.modules.auth.password import hash_password
from app.modules.auth.repository import UserRepository, UserRoleRepository
from app.modules.organization.models import (
    Branch,
    OperationalLocation,
    Organization,
    Permission,
    Role,
    Warehouse,
)
from app.modules.organization.permissions_catalog import (
    CANONICAL_PERMISSIONS_CATALOG,
    CANONICAL_ROLE_BASELINES,
)
from app.modules.organization.repository import (
    BranchRepository,
    OperationalLocationRepository,
    OrganizationRepository,
    PermissionRepository,
    RolePermissionRepository,
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
    perm_repo = PermissionRepository()
    role_perm_repo = RolePermissionRepository()
    user_repo = UserRepository()
    user_role_repo = UserRoleRepository()

    try:
        # --- 1. Canonical Permissions Catalog ---
        for p_data in CANONICAL_PERMISSIONS_CATALOG:
            code = p_data["code"]
            assert isinstance(code, str)
            existing_perm = perm_repo.get_by_code(db, code)
            if not existing_perm:
                perm = Permission(
                    code=code,
                    name=str(p_data["name"]),
                    description=str(p_data["description"]) if p_data["description"] else None,
                    category=str(p_data["category"]),
                    resource=str(p_data["resource"]),
                    action=str(p_data["action"]),
                    risk_level=str(p_data["risk_level"]),
                    is_system=True,
                    is_active=True,
                    future_phase_owner=str(p_data["future_phase_owner"])
                    if p_data["future_phase_owner"]
                    else None,
                )
                perm_repo.create(db, perm)
                print(f"Permission created: {code}")

        db.flush()

        # --- 2. Canonical 10 Logistics System Roles ---
        canonical_system_roles = [
            (
                "PURCHASING",
                "Encargado de Compras y Abastecimiento",
                "Gestión de requerimientos, cotizaciones y órdenes de compra",
            ),
            (
                "RECEIVING",
                "Especialista de Recepción y Descarga",
                "Recepción física en muelle, cotejo contra guía y registro de mermas",
            ),
            (
                "QUALITY",
                "Inspector de Control de Calidad y Cuarentena",
                "Inspección técnica, gestión de cuarentena y evaluación de conformidad",
            ),
            (
                "WAREHOUSE",
                "Operador de Almacén y Putaway",
                "Ubicación física en racks, putaway, picking y reabastecimiento interno",
            ),
            (
                "INVENTORY",
                "Controlador de Inventarios y Stock",
                "Control de stock, conteos cíclicos, conciliación de kardex y transferencias",
            ),
            (
                "DISPATCH",
                "Coordinador de Despacho y Packing",
                "Consolidación, packing, emisión de actas de despacho y carga vehicular",
            ),
            (
                "TRANSPORT",
                "Planificador de Transporte y Rutas",
                "Planificación de rutas, cubicaje de flota y asignación de conductores",
            ),
            (
                "DRIVER",
                "Conductor y Transportista",
                "Operación de viaje en ruta, monitoreo GPS y confirmación de entrega",
            ),
            (
                "AUDITOR",
                "Auditor Técnico y de Trazabilidad",
                "Inspección de trazabilidad, bitácoras y cumplimiento SoD sin mutación",
            ),
            (
                "MANAGEMENT",
                "Gerencia y Dirección Logística",
                "Supervisión estratégica de KPIs, políticas y aprobación de operaciones críticas",
            ),
        ]

        for code, name, desc in canonical_system_roles:
            sys_role = role_repo.get_by_code(db, code, organization_id=None)
            if not sys_role:
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
                db.flush()
                print(f"System Role created: {code}")

            # Assign Baseline Permissions
            baseline_codes = CANONICAL_ROLE_BASELINES.get(code, [])
            if baseline_codes:
                assigned_existing = role_perm_repo.list_permissions_by_role(db, sys_role.id)
                assigned_existing_codes = {p.code for p in assigned_existing}
                missing_codes = [c for c in baseline_codes if c not in assigned_existing_codes]
                if missing_codes or len(assigned_existing) != len(baseline_codes):
                    perms = perm_repo.list_by_codes(db, baseline_codes)
                    role_perm_repo.set_role_permissions(db, sys_role.id, [p.id for p in perms])
                    print(f"Updated {len(perms)} baseline permissions to {code}")

        # --- 3. Demo Organization ---
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

        # --- 4. Demo Custom Role ---
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
            db.flush()
            print(f"Demo Custom Role created: {custom_role.code}")

        # Assign realistic permissions to Demo Custom Role
        demo_perm_codes = [
            "organization.read",
            "branch.read",
            "warehouse.read",
            "quality.read",
            "quality.inspect",
        ]
        assigned_demo_perms = role_perm_repo.list_permissions_by_role(db, custom_role.id)
        if not assigned_demo_perms:
            demo_perms = perm_repo.list_by_codes(db, demo_perm_codes)
            role_perm_repo.set_role_permissions(db, custom_role.id, [p.id for p in demo_perms])
            print(f"Assigned {len(demo_perms)} permissions to DEMO-ROLE-QC")

        # --- 5. Branch 1: Lima ---
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

        # --- 6. Branch 2: Arequipa ---
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

        # --- 7. Demo Realistic Users (F008) ---
        demo_users_spec = [
            (
                "gerencia.demo@logistica.local",
                "Gerencia General Demo",
                "MANAGEMENT",
            ),
            (
                "almacen.demo@logistica.local",
                "Operador Almacén Demo",
                "WAREHOUSE",
            ),
            (
                "auditor.demo@logistica.local",
                "Auditor de Control Demo",
                "AUDITOR",
            ),
        ]

        demo_password = settings.DEMO_USER_PASSWORD
        demo_password_hash = hash_password(demo_password)

        for email, display_name, role_code in demo_users_spec:
            norm_email = email.strip().lower()
            u = user_repo.get_by_email_normalized(db, norm_email)
            if not u:
                u = User(
                    organization_id=demo_org.id,
                    email=email,
                    email_normalized=norm_email,
                    display_name=display_name,
                    password_hash=demo_password_hash,
                    is_active=True,
                    is_test_data=True,
                )
                user_repo.create(db, u)
                db.flush()
                print(f"Demo User created: {email}")
            else:
                # Rotate password to current settings.DEMO_USER_PASSWORD
                u.password_hash = demo_password_hash
                db.flush()

            # Assign Role
            role = role_repo.get_by_code(db, role_code, organization_id=None)
            if role:
                user_role_repo.set_user_roles(db, u.id, [role.id])
                print(f"Assigned role {role_code} to {email}")

            # Reset MFA and Step-Up state for clean test baseline
            from app.modules.auth.models import StepUpChallenge, StepUpGrant, UserMfaFactor

            db.query(StepUpGrant).filter(StepUpGrant.user_id == u.id).delete()
            db.query(StepUpChallenge).filter(StepUpChallenge.user_id == u.id).delete()
            db.query(UserMfaFactor).filter(UserMfaFactor.user_id == u.id).delete()

        # --- 5. Canonical Document Catalog ---
        from app.modules.documents.service import DocumentCatalogService

        doc_stats = DocumentCatalogService.load_canonical_catalog(db)
        print(f"Canonical Document Catalog synchronized: {doc_stats}")

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
