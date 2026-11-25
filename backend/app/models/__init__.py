"""SQLAlchemy ORM models package.

Models for transit routes, stops, trips, ridership records, and optimization scores
will be declared here in subsequent implementation modules.
"""
from app.database.session import Base

__all__ = ["Base"]
