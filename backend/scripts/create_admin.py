"""Ensure the default admin user exists."""

from app.core.database import SessionLocal
from app.services.bootstrap_service import BootstrapService

def main() -> None:
    with SessionLocal() as db:
        BootstrapService(db).ensure_defaults()
    print("Admin user ensured.")


if __name__ == "__main__":
    main()
