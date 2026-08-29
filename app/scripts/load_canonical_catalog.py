"""
Standalone loader for canonical document catalog (safe for all environments).
Does NOT create demo users, fake orders, or fake operational records.
"""

from sqlalchemy.orm import Session

from app.db.connection import SessionLocal
from app.modules.documents.service import DocumentCatalogService
from app.modules.organization.models import Permission
from app.modules.organization.permissions_catalog import (
    CANONICAL_PERMISSIONS_CATALOG,
    CANONICAL_ROLE_BASELINES,
)
from app.modules.organization.repository import (
    PermissionRepository,
    RolePermissionRepository,
    RoleRepository,
)


def load_canonical() -> None:
    db: Session = SessionLocal()
    perm_repo = PermissionRepository()
    role_repo = RoleRepository()
    role_perm_repo = RolePermissionRepository()

    try:
        # 1. Sync permissions
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

        # 2. Sync role baselines
        for role_code, perm_codes in CANONICAL_ROLE_BASELINES.items():
            role = role_repo.get_by_code(db, role_code, organization_id=None)
            if role:
                perm_ids = []
                for p_code in perm_codes:
                    p = perm_repo.get_by_code(db, p_code)
                    if p:
                        perm_ids.append(p.id)
                role_perm_repo.set_role_permissions(db, role.id, perm_ids)

        # 3. Sync canonical document catalog
        stats = DocumentCatalogService.load_canonical_catalog(db)
        print(f"Canonical catalog loaded successfully: {stats}")
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error loading canonical catalog: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    load_canonical()
