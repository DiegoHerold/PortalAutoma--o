"""Ensure the default admin user exists."""

from infrastructure.database import SessionLocal
from bootstrap.defaults import BootstrapService

def main() -> None:
    with SessionLocal() as db:
        BootstrapService(db).ensure_defaults()
    print("Admin user ensured.")


if __name__ == "__main__":
    main()
