"""Seed roles, categories and default admin user."""

from infrastructure.database import SessionLocal
from bootstrap.defaults import BootstrapService

def main() -> None:
    with SessionLocal() as db:
        BootstrapService(db).ensure_defaults()
    print("Default roles, categories and admin user ensured.")


if __name__ == "__main__":
    main()
