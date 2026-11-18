import argparse

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import ExternalIdentity, User
from app.models import PasswordCredential
from app.passwords import enabled, queue_link
from pydantic import TypeAdapter, EmailStr


def main():
    parser = argparse.ArgumentParser(description="Provision tracker membership using verified external identity identifiers.")
    parser.add_argument("command", choices=["bootstrap-admin", "provision-user"])
    parser.add_argument("--issuer")
    parser.add_argument("--subject")
    parser.add_argument("--local", action="store_true", help="Create a local account and email a password setup link")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", choices=["administrator", "member"], default="member")
    args = parser.parse_args()
    if args.local:
        enabled()
        args.email = str(TypeAdapter(EmailStr).validate_python(args.email))
        if args.issuer or args.subject:
            parser.error("--local cannot be combined with --issuer or --subject")
    elif not args.issuer or not args.subject:
        parser.error("External accounts require --issuer and --subject")
    with SessionLocal() as db:
        if args.command == "bootstrap-admin" and db.scalar(select(func.count()).select_from(User).where(User.role == "administrator")):
            parser.exit(1, "An administrator already exists; bootstrap is disabled.\n")
        if args.local:
            if db.scalar(select(PasswordCredential).where(PasswordCredential.login_email == args.email.casefold())):
                parser.exit(1, "A local account already uses this login email.\n")
            user = User(name=args.name, email=args.email, role="administrator" if args.command == "bootstrap-admin" else args.role)
            db.add(user)
            db.flush()
            credential = PasswordCredential(user_id=user.id, login_email=args.email.casefold())
            db.add(credential)
            queue_link(db, user, credential, False)
            db.commit()
            print(f"Provisioned {user.name} ({user.id}); password invitation queued.")
            return
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
