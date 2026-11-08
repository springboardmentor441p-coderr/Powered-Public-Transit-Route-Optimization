import sys
import pathlib

# Ensure the project root is on sys.path so imports work when script is executed directly
project_root = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from backend.app.db import engine, Base

def main():
    # Create all tables defined in models.py
    Base.metadata.create_all(bind=engine)
    print("[SCHEMA] All tables created successfully.")

if __name__ == "__main__":
    main()

