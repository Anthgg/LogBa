import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.modules.documents.canonical_catalog import (
    CANONICAL_DOCUMENT_FAMILIES,
    CANONICAL_DOCUMENT_TYPES,
    CANONICAL_RETENTION_POLICIES,
)
from app.modules.documents.models import (
    DocumentFamily,
    DocumentRetentionPolicy,
    DocumentType,
    DocumentTypeVersion,
)
from app.modules.documents.schemas import (
    DocumentFamilyCreate,
    DocumentRetentionPolicyCreate,
    DocumentTypeCreate,
    DocumentTypeUpdate,
    DocumentTypeVersionCreate,
)
from app.shared.audit.contracts import AuditContext
from app.shared.audit.service import AuditService

audit_service = AuditService()


class DocumentCatalogService:
    """Core domain service for Document Catalog & Versioning management."""

    @staticmethod
    def get_families(db: Session, active_only: bool = False) -> List[DocumentFamily]:
        stmt = select(DocumentFamily).order_by(DocumentFamily.code)
        if active_only:
            stmt = stmt.where(DocumentFamily.is_active.is_(True))
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_family_by_id(db: Session, family_id: uuid.UUID) -> Optional[DocumentFamily]:
        return db.get(DocumentFamily, family_id)

    @staticmethod
    def get_family_by_code(db: Session, code: str) -> Optional[DocumentFamily]:
        stmt = select(DocumentFamily).where(DocumentFamily.code == code.upper())
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create_family(
        db: Session,
        payload: DocumentFamilyCreate,
        context: Optional[AuditContext] = None,
    ) -> DocumentFamily:
        code_upper = payload.code.strip().upper()
        existing = db.execute(
            select(DocumentFamily).where(DocumentFamily.code == code_upper)
        ).scalar_one_or_none()
        if existing:
            raise ValueError(f"Ya existe una familia documental con el código '{code_upper}'")

        family = DocumentFamily(
            code=code_upper,
            name=payload.name.strip(),
            description=payload.description.strip() if payload.description else None,
            is_active=payload.is_active,
        )
        db.add(family)
        db.flush()

        if context:
            audit_service.record_event(
                db=db,
                context=context,
                resource_type="document_family",
                action="document_family.created",
                result="SUCCESS",
                resource_id=family.id,
                after_data={
                    "code": family.code,
                    "name": family.name,
                    "is_active": family.is_active,
                },
            )
        db.commit()
        db.refresh(family)
        return family

    @staticmethod
    def get_retention_policies(
        db: Session, active_only: bool = False
    ) -> List[DocumentRetentionPolicy]:
        stmt = select(DocumentRetentionPolicy).order_by(DocumentRetentionPolicy.code)
        if active_only:
            stmt = stmt.where(DocumentRetentionPolicy.is_active.is_(True))
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_retention_policy_by_id(
        db: Session, policy_id: uuid.UUID
    ) -> Optional[DocumentRetentionPolicy]:
        return db.get(DocumentRetentionPolicy, policy_id)

    @staticmethod
    def get_retention_policy_by_code(db: Session, code: str) -> Optional[DocumentRetentionPolicy]:
        stmt = select(DocumentRetentionPolicy).where(DocumentRetentionPolicy.code == code.upper())
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create_retention_policy(
        db: Session,
        payload: DocumentRetentionPolicyCreate,
        context: Optional[AuditContext] = None,
    ) -> DocumentRetentionPolicy:
        code_upper = payload.code.strip().upper()
        existing = db.execute(
            select(DocumentRetentionPolicy).where(DocumentRetentionPolicy.code == code_upper)
        ).scalar_one_or_none()
        if existing:
            raise ValueError(f"Ya existe una política de retención con el código '{code_upper}'")

        policy = DocumentRetentionPolicy(
            code=code_upper,
            name=payload.name.strip(),
            description=payload.description.strip() if payload.description else None,
            retention_days=payload.retention_days,
            retain_forever=payload.retain_forever,
            legal_hold_supported=payload.legal_hold_supported,
            is_active=payload.is_active,
        )
        db.add(policy)
        db.flush()

        if context:
            audit_service.record_event(
                db=db,
                context=context,
                resource_type="document_retention_policy",
                action="document_retention_policy.created",
                result="SUCCESS",
                resource_id=policy.id,
                after_data={
                    "code": policy.code,
                    "name": policy.name,
                    "retention_days": policy.retention_days,
                },
            )
        db.commit()
        db.refresh(policy)
        return policy

    @staticmethod
    def get_document_types(
        db: Session,
        family_id: Optional[uuid.UUID] = None,
        scope: Optional[str] = None,
        active_only: bool = False,
    ) -> List[DocumentType]:
        stmt = (
            select(DocumentType)
            .options(
                joinedload(DocumentType.family),
                joinedload(DocumentType.versions).joinedload(DocumentTypeVersion.retention_policy),
            )
            .order_by(DocumentType.code)
        )
        if family_id:
            stmt = stmt.where(DocumentType.family_id == family_id)
        if scope:
            stmt = stmt.where(DocumentType.document_scope == scope.upper())
        if active_only:
            stmt = stmt.where(DocumentType.is_active.is_(True))

        return list(db.execute(stmt).unique().scalars().all())

    @staticmethod
    def get_document_type_by_id(db: Session, type_id: uuid.UUID) -> Optional[DocumentType]:
        stmt = (
            select(DocumentType)
            .options(
                joinedload(DocumentType.family),
                joinedload(DocumentType.versions).joinedload(DocumentTypeVersion.retention_policy),
            )
            .where(DocumentType.id == type_id)
        )
        return db.execute(stmt).unique().scalar_one_or_none()

    @staticmethod
    def get_document_type_by_code(db: Session, code: str) -> Optional[DocumentType]:
        stmt = (
            select(DocumentType)
            .options(
                joinedload(DocumentType.family),
                joinedload(DocumentType.versions).joinedload(DocumentTypeVersion.retention_policy),
            )
            .where(DocumentType.code == code.upper())
        )
        return db.execute(stmt).unique().scalar_one_or_none()

    @staticmethod
    def get_versions(db: Session, type_id: uuid.UUID) -> List[DocumentTypeVersion]:
        stmt = (
            select(DocumentTypeVersion)
            .options(joinedload(DocumentTypeVersion.retention_policy))
            .where(DocumentTypeVersion.document_type_id == type_id)
            .order_by(DocumentTypeVersion.version_number.desc())
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_version_by_number(
        db: Session, type_id: uuid.UUID, version_number: int
    ) -> Optional[DocumentTypeVersion]:
        stmt = (
            select(DocumentTypeVersion)
            .options(joinedload(DocumentTypeVersion.retention_policy))
            .where(
                DocumentTypeVersion.document_type_id == type_id,
                DocumentTypeVersion.version_number == version_number,
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create_document_type(
        db: Session,
        payload: DocumentTypeCreate,
        context: Optional[AuditContext] = None,
    ) -> DocumentType:
        code_upper = payload.code.strip().upper()
        existing = db.execute(
            select(DocumentType).where(DocumentType.code == code_upper)
        ).scalar_one_or_none()
        if existing:
            raise ValueError(f"Ya existe un tipo documental con el código '{code_upper}'")

        family = db.get(DocumentFamily, payload.family_id)
        if not family:
            raise ValueError(f"La familia documental especificada '{payload.family_id}' no existe")

        doc_type = DocumentType(
            code=code_upper,
            name=payload.name.strip(),
            description=payload.description.strip() if payload.description else None,
            family_id=payload.family_id,
            document_scope=payload.document_scope,
            is_active=payload.is_active,
            phase_owner=payload.phase_owner,
        )
        db.add(doc_type)
        db.flush()

        user_id = context.actor_id if context else None

        # If initial version payload is provided, create version 1
        if payload.initial_version:
            retention = db.get(DocumentRetentionPolicy, payload.initial_version.retention_policy_id)
            if not retention:
                raise ValueError("La política de retención especificada no existe")

            now_utc = datetime.now(timezone.utc)
            initial_v = DocumentTypeVersion(
                document_type_id=doc_type.id,
                version_number=1,
                schema_definition=[
                    f.model_dump() for f in payload.initial_version.schema_definition
                ],
                emission_rules=payload.initial_version.emission_rules.model_dump(),
                status_definition=payload.initial_version.status_definition,
                template_key=payload.initial_version.template_key,
                retention_policy_id=payload.initial_version.retention_policy_id,
                read_permission=payload.initial_version.read_permission,
                emit_permission=payload.initial_version.emit_permission,
                download_permission=payload.initial_version.download_permission,
                reprint_permission=payload.initial_version.reprint_permission,
                void_permission=payload.initial_version.void_permission,
                effective_from=now_utc,
                is_current=True,
                created_by_user_id=user_id,
            )
            db.add(initial_v)
            db.flush()

        if context:
            audit_service.record_event(
                db=db,
                context=context,
                resource_type="document_type",
                action="document_type.created",
                result="SUCCESS",
                resource_id=doc_type.id,
                after_data={
                    "code": doc_type.code,
                    "name": doc_type.name,
                    "scope": doc_type.document_scope,
                    "family_id": str(doc_type.family_id),
                },
            )
        db.commit()
        return DocumentCatalogService.get_document_type_by_id(db, doc_type.id)  # type: ignore

    @staticmethod
    def update_document_type(
        db: Session,
        type_id: uuid.UUID,
        payload: DocumentTypeUpdate,
        context: Optional[AuditContext] = None,
    ) -> DocumentType:
        doc_type = db.get(DocumentType, type_id)
        if not doc_type:
            raise ValueError("Tipo documental no encontrado")

        old_values = {
            "name": doc_type.name,
            "description": doc_type.description,
            "is_active": doc_type.is_active,
            "phase_owner": doc_type.phase_owner,
        }

        if payload.name is not None:
            doc_type.name = payload.name.strip()
        if payload.description is not None:
            doc_type.description = payload.description.strip()
        if payload.is_active is not None:
            doc_type.is_active = payload.is_active
        if payload.phase_owner is not None:
            doc_type.phase_owner = payload.phase_owner

        db.flush()

        if context:
            action_name = (
                "document_type.updated"
                if payload.is_active == old_values["is_active"]
                else (
                    "document_type.activated" if doc_type.is_active else "document_type.deactivated"
                )
            )
            audit_service.record_event(
                db=db,
                context=context,
                resource_type="document_type",
                action=action_name,
                result="SUCCESS",
                resource_id=doc_type.id,
                before_data=old_values,
                after_data={
                    "name": doc_type.name,
                    "description": doc_type.description,
                    "is_active": doc_type.is_active,
                    "phase_owner": doc_type.phase_owner,
                },
            )
        db.commit()
        return DocumentCatalogService.get_document_type_by_id(db, doc_type.id)  # type: ignore

    @staticmethod
    def create_new_version(
        db: Session,
        type_id: uuid.UUID,
        payload: DocumentTypeVersionCreate,
        context: Optional[AuditContext] = None,
    ) -> DocumentTypeVersion:
        # 1. Lock document_type row to prevent concurrency race conditions
        stmt_lock = select(DocumentType).where(DocumentType.id == type_id).with_for_update()
        doc_type = db.execute(stmt_lock).scalar_one_or_none()
        if not doc_type:
            raise ValueError("Tipo documental no encontrado")

        retention = db.get(DocumentRetentionPolicy, payload.retention_policy_id)
        if not retention:
            raise ValueError("La política de retención especificada no existe")

        # 2. Get highest version number
        stmt_max = (
            select(DocumentTypeVersion.version_number)
            .where(DocumentTypeVersion.document_type_id == type_id)
            .order_by(DocumentTypeVersion.version_number.desc())
        )
        latest_version = db.execute(stmt_max).scalars().first() or 0
        next_version_number = latest_version + 1

        now_utc = datetime.now(timezone.utc)
        user_id = context.actor_id if context else None

        # 3. Close previous current version
        stmt_curr = select(DocumentTypeVersion).where(
            DocumentTypeVersion.document_type_id == type_id,
            DocumentTypeVersion.is_current.is_(True),
        )
        current_versions = db.execute(stmt_curr).scalars().all()
        for v in current_versions:
            v.is_current = False
            v.effective_to = now_utc

        # 4. Create new version
        new_version = DocumentTypeVersion(
            document_type_id=type_id,
            version_number=next_version_number,
            schema_definition=[f.model_dump() for f in payload.schema_definition],
            emission_rules=payload.emission_rules.model_dump(),
            status_definition=payload.status_definition,
            template_key=payload.template_key,
            retention_policy_id=payload.retention_policy_id,
            read_permission=payload.read_permission,
            emit_permission=payload.emit_permission,
            download_permission=payload.download_permission,
            reprint_permission=payload.reprint_permission,
            void_permission=payload.void_permission,
            effective_from=now_utc,
            is_current=True,
            created_by_user_id=user_id,
        )
        db.add(new_version)
        db.flush()

        # 5. Audit creation of new version
        if context:
            audit_service.record_event(
                db=db,
                context=context,
                resource_type="document_type_version",
                action="document_type.version.created",
                result="SUCCESS",
                resource_id=new_version.id,
                after_data={
                    "document_type_id": str(type_id),
                    "document_type_code": doc_type.code,
                    "version_number": next_version_number,
                    "template_key": new_version.template_key,
                    "retention_policy_id": str(payload.retention_policy_id),
                },
            )
        db.commit()
        db.refresh(new_version)
        return new_version

    @staticmethod
    def load_canonical_catalog(db: Session) -> Dict[str, int]:
        """Idempotently seed and sync canonical document families,
        retention policies, and document types.
        """
        created_families = 0
        created_retentions = 0
        created_types = 0
        created_versions = 0

        # 1. Seed Families
        family_map: Dict[str, DocumentFamily] = {}
        for f_data in CANONICAL_DOCUMENT_FAMILIES:
            existing = db.execute(
                select(DocumentFamily).where(DocumentFamily.code == f_data["code"])
            ).scalar_one_or_none()
            if not existing:
                fam = DocumentFamily(
                    code=f_data["code"],
                    name=f_data["name"],
                    description=f_data.get("description"),
                    is_active=True,
                )
                db.add(fam)
                db.flush()
                family_map[f_data["code"]] = fam
                created_families += 1
            else:
                family_map[f_data["code"]] = existing

        # 2. Seed Retention Policies
        retention_map: Dict[str, DocumentRetentionPolicy] = {}
        for r_data in CANONICAL_RETENTION_POLICIES:
            existing_ret = db.execute(
                select(DocumentRetentionPolicy).where(
                    DocumentRetentionPolicy.code == r_data["code"]
                )
            ).scalar_one_or_none()
            if not existing_ret:
                ret = DocumentRetentionPolicy(
                    code=r_data["code"],
                    name=r_data["name"],
                    description=r_data.get("description"),
                    retention_days=r_data.get("retention_days"),
                    retain_forever=r_data.get("retain_forever", False),
                    legal_hold_supported=r_data.get("legal_hold_supported", True),
                    is_active=True,
                )
                db.add(ret)
                db.flush()
                retention_map[r_data["code"]] = ret
                created_retentions += 1
            else:
                retention_map[r_data["code"]] = existing_ret

        # 3. Seed Document Types and Initial Version 1
        now_utc = datetime.now(timezone.utc)
        for t_data in CANONICAL_DOCUMENT_TYPES:
            existing_type = db.execute(
                select(DocumentType).where(DocumentType.code == t_data["code"])
            ).scalar_one_or_none()

            family = family_map[t_data["family_code"]]
            retention = retention_map[t_data["retention_code"]]

            if not existing_type:
                new_type = DocumentType(
                    code=t_data["code"],
                    name=t_data["name"],
                    description=t_data.get("description"),
                    family_id=family.id,
                    document_scope=t_data["document_scope"],
                    phase_owner=t_data["phase_owner"],
                    is_active=True,
                )
                db.add(new_type)
                db.flush()
                created_types += 1

                # Create version 1
                v1 = DocumentTypeVersion(
                    document_type_id=new_type.id,
                    version_number=1,
                    schema_definition=t_data["schema_definition"],
                    emission_rules=t_data["emission_rules"],
                    status_definition=t_data["status_definition"],
                    template_key=t_data.get("template_key"),
                    retention_policy_id=retention.id,
                    read_permission="documents.read",
                    emit_permission="documents.emit",
                    download_permission="documents.download",
                    reprint_permission="documents.reprint",
                    void_permission="documents.void",
                    effective_from=now_utc,
                    is_current=True,
                )
                db.add(v1)
                db.flush()
                created_versions += 1

        db.commit()
        return {
            "families": created_families,
            "retention_policies": created_retentions,
            "document_types": created_types,
            "versions": created_versions,
        }
