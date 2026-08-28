import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.connection import SessionLocal
from app.modules.organization.models import (
    Branch,
    Organization,
    Warehouse,
)
from app.modules.organization.schemas import (
    BranchCreate,
    LocationCreate,
    OrganizationCreate,
    WarehouseCreate,
)
from app.modules.organization.service import (
    BranchService,
    OrganizationService,
    WarehouseService,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_demo")

settings = get_settings()


def run_seed() -> None:
    """Seeds realistic synthetic demo data for F004 into PostgreSQL.

    Protected against execution in production.
    """
    if settings.is_production or settings.APP_ENV.lower() == "production":
        raise RuntimeError(
            "CRITICAL ERROR: Synthetic demo data cannot be seeded in PRODUCTION environment."
        )

    logger.info(
        "Running realistic synthetic data seeding (Environment: %s)...",
        settings.APP_ENV,
    )

    db: Session = SessionLocal()
    try:
        org_service = OrganizationService()
        branch_service = BranchService()
        wh_service = WarehouseService()

        # 1. Organization
        org_code = "DEMO-ORG-001"
        existing_org = db.query(Organization).filter(Organization.code == org_code).first()
        if not existing_org:
            org = org_service.create_organization(
                db,
                OrganizationCreate(
                    code=org_code,
                    name="Organización Logística Demo",
                    is_active=True,
                    is_test_data=True,
                ),
            )
            logger.info("Created Demo Organization: %s (%s)", org.name, org.id)
        else:
            org = existing_org
            logger.info("Demo Organization already exists: %s (%s)", org.name, org.id)

        # 2. Branch 1: Sede Lima
        lim_code = "DEMO-LIM"
        existing_lim = (
            db.query(Branch)
            .filter(Branch.organization_id == org.id, Branch.code == lim_code)
            .first()
        )
        if not existing_lim:
            b_lima = branch_service.create_branch(
                db,
                org.id,
                BranchCreate(
                    code=lim_code,
                    name="Sede Lima Demo",
                    location=LocationCreate(
                        label="Sede Lima Principal",
                        address_line1="Av. Argentina 2450",
                        address_line2="Zona Industrial Callao",
                        district="Callao",
                        province="Callao",
                        department="Lima",
                        country_code="PE",
                        latitude=-12.0464,
                        longitude=-77.0428,
                    ),
                    is_active=True,
                    is_test_data=True,
                ),
            )
            logger.info("Created Demo Branch: %s (%s)", b_lima.name, b_lima.id)
        else:
            b_lima = existing_lim
            logger.info("Demo Branch already exists: %s", b_lima.name)

        # 3. Warehouses for Sede Lima
        # Warehouse 1: Shared location with Sede Lima
        wh1_code = "DEMO-LIM-ALM-01"
        if (
            not db.query(Warehouse)
            .filter(Warehouse.branch_id == b_lima.id, Warehouse.code == wh1_code)
            .first()
        ):
            wh1 = wh_service.create_warehouse(
                db,
                b_lima.id,
                WarehouseCreate(
                    code=wh1_code,
                    name="Almacén Central Demo",
                    use_branch_location=True,
                    is_active=True,
                    is_test_data=True,
                ),
            )
            logger.info(
                "Created Demo Warehouse 1 (Shared Location): %s (%s)",
                wh1.name,
                wh1.id,
            )

        # Warehouse 2: Custom location
        wh2_code = "DEMO-LIM-ALM-02"
        if (
            not db.query(Warehouse)
            .filter(Warehouse.branch_id == b_lima.id, Warehouse.code == wh2_code)
            .first()
        ):
            wh2 = wh_service.create_warehouse(
                db,
                b_lima.id,
                WarehouseCreate(
                    code=wh2_code,
                    name="Almacén Secundario Demo",
                    use_branch_location=False,
                    custom_location=LocationCreate(
                        label="Almacén Secundario Callao",
                        address_line1="Av. Elmer Faucett 3100",
                        address_line2="Centro Logístico Aeropuerto",
                        district="Callao",
                        province="Callao",
                        department="Lima",
                        country_code="PE",
                        latitude=-12.0234,
                        longitude=-77.1089,
                    ),
                    is_active=True,
                    is_test_data=True,
                ),
            )
            logger.info(
                "Created Demo Warehouse 2 (Custom Location): %s (%s)",
                wh2.name,
                wh2.id,
            )

        # 4. Branch 2: Sede Arequipa
        aqp_code = "DEMO-AQP"
        existing_aqp = (
            db.query(Branch)
            .filter(Branch.organization_id == org.id, Branch.code == aqp_code)
            .first()
        )
        if not existing_aqp:
            b_aqp = branch_service.create_branch(
                db,
                org.id,
                BranchCreate(
                    code=aqp_code,
                    name="Sede Arequipa Demo",
                    location=LocationCreate(
                        label="Sede Arequipa",
                        address_line1="Parque Industrial Mz. A Lt. 4",
                        address_line2=None,
                        district="Cerro Colorado",
                        province="Arequipa",
                        department="Arequipa",
                        country_code="PE",
                        latitude=-16.4090,
                        longitude=-71.5375,
                    ),
                    is_active=True,
                    is_test_data=True,
                ),
            )
            logger.info("Created Demo Branch: %s (%s)", b_aqp.name, b_aqp.id)
        else:
            b_aqp = existing_aqp
            logger.info("Demo Branch already exists: %s", b_aqp.name)

        # 5. Warehouse for Sede Arequipa
        wh3_code = "DEMO-AQP-ALM-01"
        if (
            not db.query(Warehouse)
            .filter(Warehouse.branch_id == b_aqp.id, Warehouse.code == wh3_code)
            .first()
        ):
            wh3 = wh_service.create_warehouse(
                db,
                b_aqp.id,
                WarehouseCreate(
                    code=wh3_code,
                    name="Almacén Arequipa Demo",
                    use_branch_location=True,
                    is_active=True,
                    is_test_data=True,
                ),
            )
            logger.info("Created Demo Warehouse 3: %s (%s)", wh3.name, wh3.id)

        logger.info("Seeding completed successfully!")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
