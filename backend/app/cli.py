import argparse

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import ExternalIdentity, User


def main():
    parser = argparse.ArgumentParser(description="Provision tracker membership using verified external identity identifiers.")
    parser.add_argument("command", choices=["bootstrap-admin", "provision-user"])
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", choices=["administrator", "member", "reader"], default="member")
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.command == "bootstrap-admin" and db.scalar(select(func.count()).select_from(User).where(User.role == "administrator")):
            parser.exit(1, "An administrator already exists; bootstrap is disabled.\n")
        identity = db.scalar(select(ExternalIdentity).where(ExternalIdentity.issuer == args.issuer, ExternalIdentity.subject == args.subject))
        user = db.get(User, identity.user_id) if identity else User(name=args.name, email=args.email)
        user.role = "administrator" if args.command == "bootstrap-admin" else args.role
        if not identity:
            db.add(user)
            db.flush()
            db.add(ExternalIdentity(user_id=user.id, issuer=args.issuer, subject=args.subject))
        db.commit()
        print(f"Provisioned {user.name} as {user.role} ({user.id}).")


if __name__ == "__main__":
    main()
