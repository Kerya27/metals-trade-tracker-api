"""Promote an existing user to admin.

Usage:
    python -m scripts.make_admin user@example.cz
    docker compose exec api python -m scripts.make_admin user@example.cz
"""

import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Role, User


def make_admin(email: str) -> int:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            print(f"No user with email {email!r}. Register first via POST /api/v1/auth/register.")
            return 1
        user.role = Role.ADMIN
        db.commit()
        print(f"{user.email} is now admin.")
        return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(make_admin(sys.argv[1]))
