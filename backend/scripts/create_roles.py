"""Ensure the default roles exist."""

from infrastructure.database import SessionLocal
from app.services.bootstrap_service import BootstrapService

def main() -> None:
    with SessionLocal() as db:
        BootstrapService(db)._ensure_roles()
    print("Roles ensured.")


if __name__ == "__main__":
    main()
