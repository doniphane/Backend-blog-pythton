"""Promeut un compte existant au rôle admin.

Usage (depuis la racine du backend) :
    .venv/bin/python scripts/promote_admin.py moi@exemple.com
    .venv/bin/python scripts/promote_admin.py moi@exemple.com --demote  # rétrograde en "user"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Promeut un compte au rôle admin.")
    parser.add_argument("email", help="Email du compte à promouvoir")
    parser.add_argument(
        "--demote", action="store_true", help="Rétrograde le compte au rôle user"
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == args.email).first()
        if not user:
            print(f"Compte introuvable : {args.email}")
            return 1
        user.role = "user" if args.demote else "admin"
        db.commit()
        print(f"{user.email} -> rôle \"{user.role}\"")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
