import getpass
import sys
import uuid

from sqlalchemy.orm import Session

from app.db.connection import SessionLocal
from app.modules.auth.schemas import UserCreate
from app.modules.auth.service import AuthService
from app.shared.audit.contracts import AuditContext


def main() -> None:
    print("=== BOOTSTRAP DE USUARIO LOGISTICA ===")
    email = input("Email: ").strip()
    if not email:
        print("Error: El email no puede estar vacio.")
        sys.exit(1)

    display_name = input("Nombre a mostrar: ").strip()
    if not display_name:
        print("Error: El nombre no puede estar vacio.")
        sys.exit(1)

    org_id_str = input("Organization ID (UUID): ").strip()
    try:
        org_id = uuid.UUID(org_id_str)
    except ValueError:
        print("Error: Organization ID invalido.")
        sys.exit(1)

    role_code = input("Rol inicial (por defecto MANAGEMENT): ").strip() or "MANAGEMENT"

    password = getpass.getpass("Password (minimo 12 caracteres): ")
    password_confirm = getpass.getpass("Confirmar Password: ")

    if password != password_confirm:
        print("Error: Las contrasenas no coinciden.")
        sys.exit(1)

    if len(password) < 12:
        print("Error: La contrasena debe tener al menos 12 caracteres.")
        sys.exit(1)

    db: Session = SessionLocal()
    try:
        service = AuthService()
        user_res = service.create_user(
            db=db,
            data=UserCreate(
                organization_id=org_id,
                email=email,
                display_name=display_name,
                initial_password=password,
                role_codes=[role_code],
                is_test_data=False,
            ),
            context=AuditContext(actor_type="SYSTEM", organization_id=org_id),
        )
        print(f"Usuario creado exitosamente: {user_res.email} (ID: {user_res.id})")
    except Exception as e:
        print(f"Error al crear usuario: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
