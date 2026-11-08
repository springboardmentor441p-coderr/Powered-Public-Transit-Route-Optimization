import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.app.db import SessionLocal
from backend.app.models import Role

session = SessionLocal()
roles = session.query(Role).all()
print('Roles in DB:', [r.name for r in roles])
session.close()

