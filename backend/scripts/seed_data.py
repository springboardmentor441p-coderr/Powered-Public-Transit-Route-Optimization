import os
import sys
from sqlalchemy.orm import Session
from backend.app.db import SessionLocal, engine
from backend.app.models import Role, User, Base
from backend.app.core.config import settings
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def seed_roles(session: Session):
    for role_name in ["admin", "operator"]:
        if not session.query(Role).filter_by(name=role_name).first():
            session.add(Role(name=role_name))
    session.commit()

def seed_admin(session: Session):
    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    admin_role = session.query(Role).filter_by(name="admin").first()
    if not admin_role:
        raise Exception("Admin role not found, seed roles first")
    existing = session.query(User).filter_by(email=admin_email).first()
    if not existing:
        user = User(
            email=admin_email,
            hashed_password=get_password_hash(admin_password),
            full_name="Admin User",
            role_id=admin_role.id,
        )
        session.add(user)
        session.commit()
        print(f"[SEED] Admin user created: {admin_email}")
    else:
        print(f"[SEED] Admin user already exists: {admin_email}")

def reset_test_users(session: Session):
    session.query(User).filter(User.email.in_(["operator@example.com", "test2@example.com"])).delete(synchronize_session=False)
    session.commit()

def main(clean_test_only: bool = True):
    # Ensure all tables exist without destroying existing GTFS / operational data
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        seed_roles(session)
        seed_admin(session)
        if clean_test_only:
            reset_test_users(session)
    finally:
        session.close()

if __name__ == "__main__":
    main()
